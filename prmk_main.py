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
    arg_parser.add_argument('-pc', help='print commands', required=False, default=False)
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
                      "Cut depth",
                      "Usa funzione costo semplificata (S/N)"]
        fieldValues_df = [args.sd if args.sd is not None else DEF_SD,
                          args.gd if args.gd is not None else DEF_GD,
                          '{:.0%}'.format(args.cd) if args.cd is not None else '{:.0%}'.format(DEF_CD),
                          USE_DEF]

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
        use_avra = True if fieldValues[3] == 'S' else False

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
        r_i.do_command(xlsread_command, stdout_thru=True)

        # RUN PROGRAM ----------------------------------------------------
        print('Running program...')
        remote_output_file_path = PROGRAM_OUTPUT_PATH.format(base_input_filename)
        program_command = '{nohup}{int} {script} ' \
                          '-f "{folder}" ' \
                          '-o "{pro_out}" ' \
                          '-sd {sim_days} ' \
                          '-gd {gra_days} ' \
                          '-sv "glpk" ' \
                          '-cd {cut} ' \
                          '-s {seed} '\
                          '{avra}'\
                          '{ebang}'\
                          .format(nohup='nohup ' if batch_mode else '',
                                  int=INTERPRETER_PATH, script=MAIN_PATH,
                                  folder=xlsread_output_folder,
                                  pro_out=remote_output_file_path,
                                  sim_days=sim_days,
                                  gra_days=gra_days,
                                  cut=cut_depth,
                                  seed=14687458,
                                  avra='-ob "agent_cost_avramidis"' if use_avra else '',
                                  ebang=' > /dev/null 2>&1 &' if batch_mode else '')

        lgr.debug(program_command)
        if foreground_mode:
            r_i.do_command(program_command, pkill_on_exit=foreground_mode, stdout_thru=foreground_mode)
        else:
            transport = r_i.ssh.get_transport()
            channel = transport.open_session()
            channel.exec_command(program_command)

        # OUTPUT ----------------------------------------------------
        time.sleep(1)
        if foreground_mode:
            r_i.download_file(remote_output_file_path,
                              local_output_file_path)


