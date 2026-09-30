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
