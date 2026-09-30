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

def _mini_mutation_testing_aspect_impl(target, ctx):
    if ctx.rule.kind != "mini_test":
        return []

    src = ctx.rule.attr.src.files.to_list()[0]
    cli_files_to_run = ctx.attr._cli[DefaultInfo].files_to_run

    mutations_dir = ctx.actions.declare_directory(target.label.name + ".mutations")
    args = ctx.actions.args()
    args.add("mutate")
    args.add("list")
    args.add(src.path)
    args.add("-o")
    args.add(mutations_dir.path)
    ctx.actions.run(
        executable = cli_files_to_run,
        inputs = [src],
        outputs = [mutations_dir],
        arguments = [args],
        mnemonic = "MiniMutationList",
        progress_message = "Enumerating minilang mutations for %{label}",
    )

    return [OutputGroupInfo(_validation = depset([mutations_dir]))]

mini_mutation_testing_aspect = aspect(
    implementation = _mini_mutation_testing_aspect_impl,
    attrs = {
        "_cli": attr.label(
            default = "//cli:cli",
            executable = True,
            cfg = "exec",
        ),
    },
    doc = "Enumerates the mutations of a mini_test target's source into a tree artifact.",
)
