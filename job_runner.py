def run_print_job(env, printer, gcode_list):
    yield env.process(printer._print_loop(gcode_list))