import argparse
import json
import os
import sys
import time

import easygui
import paramiko


CONN_RETRIES = 30


def _connect(host, user, password):
    i = 1
    while True:
        print("Trying to connect to {} ({}/{})".format(host, i, CONN_RETRIES))

        try:
            ssh_client = paramiko.SSHClient()
            ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            ssh_client.connect(host, 22, username=user, password=password)
            print("Connected to {}".format(host))
            break
        except paramiko.AuthenticationException:
            print("Authentication failed when connecting to {}".format(host))
            sys.exit(1)
        except:
            print("Could not SSH to {}, waiting for it to start".format(host))
            i += 1
            time.sleep(2)

        # If we could not connect within time limit
        if i == CONN_RETRIES:
            print("Could not connect to {}. Giving up".format(host))
            sys.exit(1)

    sftp_client = ssh_client.open_sftp()
    return ssh_client, sftp_client


class RemoteInterface:
    def __init__(self, host, user, password):
        self.host = host
        self.user = user
        self.password = password
        self.pids_2_kill = []

    def __enter__(self):
        self.ssh, self.sftp = _connect(self.host, self.user, self.password)
        return self

    def do_command(self, command_str, pkill_on_exit=False, stdout_thru=False):
        command = 'echo $$; exec ' + command_str
        stdin, stdout, stderr = self.ssh.exec_command(command)
        pid = int(stdout.readline())  # first line is pid
        if pkill_on_exit:
            self.pids_2_kill.append(pid)

        if stdout_thru:
            while True:
                line = stdout.readline().rstrip('\n')
                # eline = stderr.readline().rstrip('\n')
                if line:
                    print(line)
                    continue
                # if eline:
                #     print('ERR: {}'.format(eline))
                #     continue

                if stdout.channel.exit_status_ready():
                    break

    def upload_file(self, local_path, remote_path):
        self.sftp.put(local_path, remote_path)

    def download_file(self, remote_path, local_path):
        self.sftp.get(remote_path, local_path)

    def __exit__(self, exc_type, exc_val, exc_tb):
        for pid in self.pids_2_kill:
            _stdin, _stdout, _stderr = self.ssh.exec_command('kill {}'.format(pid))
            _stdin, _stdout, _stderr = self.ssh.exec_command('pkill -p {}'.format(pid))
        self.sftp.close()
        self.ssh.close()


if __name__ == '__main__':

    # SETUP ---------------------------------------------------------

    arg_parser = argparse.ArgumentParser()
    arg_parser.add_argument('-hs', help='host', required=True)
    arg_parser.add_argument('-u', help='username', required=True)
    arg_parser.add_argument('-p', help='password', required=True)
    arg_parser.add_argument('-lf', help='local_file', required=False)
    args = arg_parser.parse_args()

    host = args.hs
    username = args.u
    password = args.p

    if args.lf is not None:
        local_input_file_path = args.lf
    else:
        local_input_file_path = easygui.fileopenbox()

    if username is None:
        with open('credential.json', 'r') as json_cr_f:
            crs = json.load(json_cr_f)
            host = crs['host']
            username = crs['username']
            password = crs['password']

    LANDING_FOLDER = '/tmp/landing/'
    INTERPRETER_PATH = '/ccvenv_0/bin/python3'
    XLSREAD_PATH = '/ccsim/ccsim/xlsread.py'
    MAIN_PATH = '/ccsim/main.py'
    PROGRAM_OUTPUT_PATH = '/ccsim/program_outputs/{}_OUT.xlsx'
    BASE_OUTPUT_FOLDER = '/ccsim/xlread_outputs'

    with RemoteInterface(host, username, password) as r_interface:

        # FILE UPLOAD ----------------------------------------------------
        print('Uploading file...')
        local_input_folder_path, input_filename = os.path.split(local_input_file_path)
        # remote_path = LANDING_FOLDER + filename
        remote_path = os.path.join(LANDING_FOLDER, input_filename)
        r_interface.upload_file(local_input_file_path, remote_path)

        # RUN XLSREAD ----------------------------------------------------
        print('Reading file...')
        base_input_filename, extension = os.path.splitext(input_filename)
        # xlsread_output_folder = os.path.join(BASE_OUTPUT_FOLDER, base_filename)
        xlsread_output_folder = BASE_OUTPUT_FOLDER + '/' + base_input_filename
        xlsread_command = '{int} {script} -f {file} -o {output}'.format(int=INTERPRETER_PATH,
                                                                        script=XLSREAD_PATH,
                                                                        file=remote_path,
                                                                        output=xlsread_output_folder)
        r_interface.do_command(xlsread_command, stdout_thru=True)

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
                                  sim_days=8,
                                  gra_days=4,
                                  cut=0.07,
                                  seed=1233232323)

        # print(program_command)
        r_interface.do_command(program_command, pkill_on_exit=True, stdout_thru=True)

        # OUTPUT ----------------------------------------------------
        time.sleep(1)
        r_interface.download_file(remote_output_file_path,
                                  os.path.join(local_input_folder_path, base_input_filename + '_OUT' + extension))


