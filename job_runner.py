def run_print_job(env, printer, gcode_commands):
    """Run a print job with the given G-code commands"""
    yield env.process(printer._print_loop(gcode_commands))
