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
USE_DEF = 'S'

DEF_SW = 0.648
DEF_AC = 0.5

if __name__ == '__main__':

    # SETUP ---------------------------------------------------------

    arg_parser = argparse.ArgumentParser()
    arg_parser.add_argument('-c', help='config', required=True)
    arg_parser.add_argument('-bt', help='batch_mode', required=True)

    # configuration can be either passed or will be asked for with easygui
    arg_parser.add_argument('-lf', help='local_file', required=False)
    arg_parser.add_argument('-of', help='output_file', required=False)
    arg_parser.add_argument('-sd', help='simulation days', required=False)
    arg_parser.add_argument('-gd', help='gradient days', required=False)
    arg_parser.add_argument('-cd', help='cut depth', required=False)
    arg_parser.add_argument('-fa', help='force alpha', required=False)
    arg_parser.add_argument('-pc', help='print commands', required=False, default=False)

    arg_parser.add_argument('-ac', help='agent activation cost', required=False)
    arg_parser.add_argument('-sw', help='skill weight', required=False)

    args = arg_parser.parse_args()

    config_filename = args.c
    batch_mode = True if args.bt == 'yes' else False
    foreground_mode = not batch_mode

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
    try:
        ssh_port = cfg['port']
    except KeyError:
        ssh_port = '22'
    username = cfg['username']
    password = cfg['password']

    # input file
    if args.lf is not None:
        local_input_file_path = args.lf
    else:
        local_input_file_path = easygui.fileopenbox('Scegli il file di input che vuoi usare')
    local_input_folder_path, input_filename = os.path.split(local_input_file_path)
    base_input_filename, extension = os.path.splitext(input_filename)

    if foreground_mode:
        # output folder
        if args.of is not None:
            local_output_file_path = args.of
        else:
            local_output_file_path = easygui.filesavebox('Scegli dove salvare il file di output',
                                                         default=base_input_filename + '_OUT' + extension)

    if args.fa is not None:
        fa = args.fa
        if fa == 'none':
            fa_string = ''
        else:
            fa = float(args.fa)
            fa_string = ' -fa {}'.format(fa)
    else:
        fa_string = ''

    # sim configuration
    if args.sd is not None and args.gd is not None and args.cd is not None:
        sim_days = args.sd
        gra_days = args.gd
        cut_depth = args.cd
        skl_wt = args.sw
        act_cost = args.ac
    else:

        msg = "Scegli i parametri di simulazione"
        title = "CCSIM Parametri"
        fieldNames = ["Giorni simulati per valutare SL",
                      "Giorni simulati per valutare gradiente",
                      "Cut depth",
                      "Usa funzione costo semplificata (S/N)",
                      "Costo attivazione agente",
                      "Peso multiskill"]
        fieldValues_df = [args.sd if args.sd is not None else DEF_SD,
                          args.gd if args.gd is not None else DEF_GD,
                          '{:.0%}'.format(args.cd) if args.cd is not None else '{:.0%}'.format(DEF_CD),
                          USE_DEF,
                          args.ac if args.sd is not None else DEF_AC,
                          args.sw if args.sd is not None else DEF_SW
                          ]

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

        while True:
            errmsg = ""
            if fieldValues[3] in ('S', 'N', 's', 'n'):
                break
            fieldValues = easygui.multenterbox(errmsg, title, fieldNames, fieldValues_df)

        sim_days = fieldValues[0]
        gra_days = fieldValues[1]
        cut_depth = str(float(fieldValues[2].rstrip('%'))/100)
        use_comapp_cost = True if fieldValues[3] == 'S' else False
        skl_wt = fieldValues[4]
        act_cost = fieldValues[5]

    with RemoteInterface(host, ssh_port, username, password) as r_i:

        # FILE UPLOAD ----------------------------------------------------
        print('Uploading file...')
        remote_path = os.path.join(LANDING_FOLDER, input_filename)
        r_i.upload_file(local_input_file_path, remote_path)

        # RUN XLSREAD ----------------------------------------------------
        print('Reading file...')
        # xlsread_output_folder = os.path.join(BASE_OUTPUT_FOLDER, base_filename)
        xlsread_output_folder = BASE_OUTPUT_FOLDER + '/' + base_input_filename
        xlsread_command = '{int} {script} -f "{file}" -o "{output}"'.format(
            int=INTERPRETER_PATH,
            script=XLSREAD_PATH,
            file=remote_path,
            output=xlsread_output_folder)

        lgr.debug(xlsread_command)
        r_i.do_command(xlsread_command, background=False)

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
                          '{avra}' \
                          '{fa}'\
                          .format(int=INTERPRETER_PATH, script=MAIN_PATH,
                                  folder=xlsread_output_folder,
                                  pro_out=remote_output_file_path,
                                  sim_days=sim_days,
                                  gra_days=gra_days,
                                  cut=cut_depth,
                                  seed=14687458,
                                  avra='-ob "agent_cost_comapp" -ac {} -sw {}'.format(act_cost, skl_wt) if use_comapp_cost else '',
                                  fa=fa_string)

        lgr.debug(program_command)
        r_i.do_command(program_command, background=batch_mode)

        # OUTPUT ----------------------------------------------------
        time.sleep(1)
        if foreground_mode:
            r_i.download_file(remote_output_file_path,
                              local_output_file_path)


