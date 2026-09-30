"""Bazel rules for minilang."""

def _mini_test_impl(ctx):
    cli = ctx.executable._cli
    src = ctx.file.src

    runner = ctx.actions.declare_file(ctx.label.name + ".sh")
    ctx.actions.expand_template(
        template = ctx.file._runner_tpl,
        output = runner,
        is_executable = True,
        substitutions = {
            "%workspace%": ctx.workspace_name or "_main",
            "%cli_short_path%": cli.short_path,
            "%src_short_path%": src.short_path,
        },
    )

    runfiles = ctx.runfiles(files = [src, cli])
    runfiles = runfiles.merge(ctx.attr._cli[DefaultInfo].default_runfiles)

    return [DefaultInfo(
        executable = runner,
        runfiles = runfiles,
    )]

mini_test = rule(
    implementation = _mini_test_impl,
    test = True,
    attrs = {
        "src": attr.label(
            allow_single_file = [".mini"],
            mandatory = True,
            doc = "The .mini source file containing test blocks to run.",
        ),
        "_cli": attr.label(
            default = "//cli:cli",
            executable = True,
            cfg = "exec",
        ),
        "_runner_tpl": attr.label(
            default = "//:runner.sh.tpl",
            allow_single_file = True,
        ),
    },
    doc = "Runs the `test` blocks of a minilang program using the //cli CLI.",
)

def _run_one_mutation(template_ctx, *, input_directories, output_directories, additional_inputs, tools, additional_params):
    cli = tools["cli"]
    src = additional_inputs["src"]
    mutations = input_directories["mutations"]
    results = output_directories["results"]

    for child in mutations.children:
        if not child.tree_relative_path.endswith("/mutation.json"):
            continue
        mid = child.tree_relative_path.split("/", 1)[0]

        mutated = template_ctx.declare_file(mid + "/mutated.mini", directory = results)
        patch_args = template_ctx.args()
        patch_args.add("mutate")
        patch_args.add("patch")
        patch_args.add("--mutation", child)
        patch_args.add("--source", src)
        patch_args.add("--output", mutated)
        template_ctx.run(
            executable = cli,
            inputs = [child, src],
            outputs = [mutated],
            arguments = [patch_args],
            progress_message = "Patching mutation " + mid,
        )

        test_xml = template_ctx.declare_file(mid + "/test.xml", directory = results)
        test_args = template_ctx.args()
        test_args.add("mutate")
        test_args.add("test")
        test_args.add(mutated)
        test_args.add("--junit-xml")
        test_args.add(test_xml)
        test_args.add("--mutation-json")
        test_args.add(child)
        template_ctx.run(
            executable = cli,
            inputs = [mutated, child],
            outputs = [test_xml],
            arguments = [test_args],
            progress_message = "Testing mutation " + mid,
        )

def _mini_mutation_testing_aspect_impl(target, ctx):
    if ctx.rule.kind != "mini_test":
        return []

    src = ctx.rule.attr.src.files.to_list()[0]
    cli_files_to_run = ctx.attr._cli[DefaultInfo].files_to_run
    cli = cli_files_to_run.executable

    mutations_dir = ctx.actions.declare_directory(target.label.name + ".mutations")
    list_args = ctx.actions.args()
    list_args.add("mutate")
    list_args.add("list")
    list_args.add(src.path)
    list_args.add("-o")
    list_args.add(mutations_dir.path)
    ctx.actions.run(
        executable = cli_files_to_run,
        inputs = [src],
        outputs = [mutations_dir],
        arguments = [list_args],
        mnemonic = "MiniMutationList",
        progress_message = "Enumerating minilang mutations for %{label}",
    )

    results_dir = ctx.actions.declare_directory(target.label.name + ".mutation_results")
    ctx.actions.map_directory(
        input_directories = {"mutations": mutations_dir},
        output_directories = {"results": results_dir},
        tools = {"cli": cli_files_to_run},
        additional_inputs = {"src": src},
        implementation = _run_one_mutation,
        mnemonic = "MiniMutationMap",
    )

    return [OutputGroupInfo(_validation = depset([results_dir]))]

mini_mutation_testing_aspect = aspect(
    implementation = _mini_mutation_testing_aspect_impl,
    attrs = {
        "_cli": attr.label(
            default = "//cli:cli",
            executable = True,
            cfg = "exec",
        ),
    },
    doc = "For each mini_test target, generates per-mutation Bazel actions via ctx.actions.map_directory. Results are surfaced through the _validation output group so surviving mutations fail the build automatically.",
)
