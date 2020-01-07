import argparse
import os
import time

import easygui

from remote_interface import RemoteInterface

DEF_SD = 32
DEF_GD = 8
DEF_CD = 0.1

if __name__ == '__main__':

    # SETUP ---------------------------------------------------------

    arg_parser = argparse.ArgumentParser()
    arg_parser.add_argument('-hs', help='host', required=True)
    arg_parser.add_argument('-u', help='username', required=True)
    arg_parser.add_argument('-p', help='password', required=True)

    # configuration can be either passed or will be asked for with easygui
    arg_parser.add_argument('-lf', help='local_file', required=False)
    arg_parser.add_argument('-of', help='local_file', required=False)
    arg_parser.add_argument('-sd', help='local_file', required=False)
    arg_parser.add_argument('-gd', help='local_file', required=False)
    arg_parser.add_argument('-cd', help='local_file', required=False)
    args = arg_parser.parse_args()

    # authentication
    host = args.hs
    username = args.u
    password = args.p

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
                          args.cd if args.cd is not None else DEF_CD]

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
        cut_depth = fieldValues[2]

    LANDING_FOLDER = '/tmp/landing/'
    INTERPRETER_PATH = '/ccvenv_0/bin/python3'
    XLSREAD_PATH = '/ccsim/ccsim/xlsread.py'
    MAIN_PATH = '/ccsim/main.py'
    PROGRAM_OUTPUT_PATH = '/ccsim/program_outputs/{}_OUT.xlsx'
    BASE_OUTPUT_FOLDER = '/ccsim/xlread_outputs'

    with RemoteInterface(host, username, password) as r_i:

        # FILE UPLOAD ----------------------------------------------------
        print('Uploading file...')
        # remote_path = LANDING_FOLDER + filename
        remote_path = os.path.join(LANDING_FOLDER, input_filename)
        r_i.upload_file(local_input_file_path, remote_path)

        # RUN XLSREAD ----------------------------------------------------
        print('Reading file...')
        # xlsread_output_folder = os.path.join(BASE_OUTPUT_FOLDER, base_filename)
        xlsread_output_folder = BASE_OUTPUT_FOLDER + '/' + base_input_filename
        xlsread_command = '{int} {script} -f {file} -o {output}'.format(int=INTERPRETER_PATH,
                                                                        script=XLSREAD_PATH,
                                                                        file=remote_path,
                                                                        output=xlsread_output_folder)
        r_i.do_command(xlsread_command, stdout_thru=True)

        # RUN PROGRAM ----------------------------------------------------
        print('Running program...')
        remote_output_file_path = PROGRAM_OUTPUT_PATH.format(base_input_filename)
        program_command = '{int} {script} ' \
                          '-f {folder} ' \
                          '-o {pro_out} ' \
                          '-sd {sim_days} ' \
                          '-gd {gra_days} ' \
                          '-sv "ipopt" ' \
                          '-cd {cut} ' \
                          '-s {seed}'\
                          .format(int=INTERPRETER_PATH, script=MAIN_PATH,
                                  folder=xlsread_output_folder,
                                  pro_out=remote_output_file_path,
                                  sim_days=sim_days,
                                  gra_days=gra_days,
                                  cut=cut_depth,
                                  seed=14687458)

        # print(program_command)
        r_i.do_command(program_command, pkill_on_exit=True, stdout_thru=True)

        # OUTPUT ----------------------------------------------------
        time.sleep(1)
        r_i.download_file(remote_output_file_path,
                          local_output_file_path)


