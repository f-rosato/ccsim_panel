import argparse
import json
import logging
import os
import sys
import time

import easygui

from remote_interface import RemoteInterface

DEF_SD = 32
DEF_GD = 8
DEF_CD = 0.1

if __name__ == '__main__':

    # SETUP ---------------------------------------------------------

    arg_parser = argparse.ArgumentParser()
    arg_parser.add_argument('-c', help='config', required=True)

    # configuration can be either passed or will be asked for with easygui
    arg_parser.add_argument('-lf', help='local_file', required=False)
    arg_parser.add_argument('-of', help='output_file', required=False)
    arg_parser.add_argument('-sd', help='simulation days', required=False)
    arg_parser.add_argument('-gd', help='gradient days', required=False)
    arg_parser.add_argument('-cd', help='cut depth', required=False)
    arg_parser.add_argument('-pc', help='print commands', required=False, default=False)
    args = arg_parser.parse_args()

    config_filename = args.c

    with open(config_filename, 'r') as config_file:
        cfg = json.load(config_file)

    lgr = logging.getLogger('ccsim_panel')
    strh = logging.StreamHandler(stream=sys.stdout)
    lgr.addHandler(strh)

    if args.pc:
        lgr.setLevel(logging.DEBUG)
    else:
        lgr.setLevel(logging.WARNING)

    # folder configuration
    LANDING_FOLDER = cfg['LANDING_FOLDER']
    INTERPRETER_PATH = cfg['INTERPRETER_PATH']
    XLSREAD_PATH = cfg['XLSREAD_PATH']
    MAIN_PATH = cfg['MAIN_PATH']
    PROGRAM_OUTPUT_PATH = cfg['PROGRAM_OUTPUT_PATH']
    BASE_OUTPUT_FOLDER = cfg['BASE_OUTPUT_FOLDER']

    # authentication
    host = cfg['host']
    username = cfg['username']
    password = cfg['password']

    # input file
    if args.lf is not None:
        local_input_file_path = args.lf
    else:
        local_input_file_path = easygui.fileopenbox('Scegli il file di input che vuoi usare')
    local_input_folder_path, input_filename = os.path.split(local_input_file_path)
    base_input_filename, extension = os.path.splitext(input_filename)

    # output folder
    if args.of is not None:
        local_output_file_path = args.of
    else:
        local_output_file_path = easygui.filesavebox('Scegli dove salvare il file di output',
                                                     default=base_input_filename + '_OUT' + extension)
    # sim configuration
    if args.sd is not None and args.gd is not None and args.cd is not None:
        sim_days = args.sd
        gra_days = args.gd
        cut_depth = args.cd
    else:

        msg = "Scegli i parametri di simulazione"
        title = "CCSIM Parametri"
        fieldNames = ["Giorni simulati per valutare SL",
                      "Giorni simulati per valutare gradiente",
                      "Cut depth"]
        fieldValues_df = [args.sd if args.sd is not None else DEF_SD,
                          args.gd if args.gd is not None else DEF_GD,
                          '{:.0%}'.format(args.cd) if args.cd is not None else '{:.0%}'.format(DEF_CD)]

        fieldValues = easygui.multenterbox(msg, title, fieldNames, fieldValues_df)

        # make sure that none of the fields was left blank
        while True:
            if fieldValues is None:
                break
            errmsg = ""
            for i in range(len(fieldNames)):
                if fieldValues[i].strip() == "":
                    errmsg += ('"%s" is a required field.\n\n' % fieldNames[i])
            if errmsg == "":
                break  # no problems found
            fieldValues = easygui.multenterbox(errmsg, title, fieldNames, fieldValues_df)

        sim_days = fieldValues[0]
        gra_days = fieldValues[1]
        cut_depth = str(float(fieldValues[2].rstrip('%'))/100)

    with RemoteInterface(host, username, password) as r_i:

        # FILE UPLOAD ----------------------------------------------------
        print('Uploading file...')
        remote_path = os.path.join(LANDING_FOLDER, input_filename)
        r_i.upload_file(local_input_file_path, remote_path)

        # RUN XLSREAD ----------------------------------------------------
        print('Reading file...')
        # xlsread_output_folder = os.path.join(BASE_OUTPUT_FOLDER, base_filename)
        xlsread_output_folder = BASE_OUTPUT_FOLDER + '/' + base_input_filename
        xlsread_command = '{int} {script} -f "{file}" -o "{output}"'.format(int=INTERPRETER_PATH,
                                                                        script=XLSREAD_PATH,
                                                                        file=remote_path,
                                                                        output=xlsread_output_folder)
        lgr.debug(xlsread_command)
        r_i.do_command(xlsread_command, stdout_thru=True)

        # RUN PROGRAM ----------------------------------------------------
        print('Running program...')
        remote_output_file_path = PROGRAM_OUTPUT_PATH.format(base_input_filename)
        program_command = '{int} {script} ' \
                          '-f "{folder}" ' \
                          '-o "{pro_out}" ' \
                          '-sd {sim_days} ' \
                          '-gd {gra_days} ' \
                          '-sv "glpk" ' \
                          '-cd {cut} ' \
                          '-s {seed} '\
                          '-ob "agent_cost_avramidis"'\
                          .format(int=INTERPRETER_PATH, script=MAIN_PATH,
                                  folder=xlsread_output_folder,
                                  pro_out=remote_output_file_path,
                                  sim_days=sim_days,
                                  gra_days=gra_days,
                                  cut=cut_depth,
                                  seed=14687458)

        lgr.debug(program_command)
        r_i.do_command(program_command, pkill_on_exit=True, stdout_thru=True)

        # OUTPUT ----------------------------------------------------
        time.sleep(1)
        r_i.download_file(remote_output_file_path,
                          local_output_file_path)


