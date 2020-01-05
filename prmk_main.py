import argparse
import json
import os
import sys
import time

import easygui
import paramiko


def _connect(host, user, password):
    i = 1
    while True:
        print("Trying to connect to {} ({}/30)".format(host, i))

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
        if i == 30:
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
                if not line:
                    break
                print(line)

    def upload_file(self, local_path, remote_path):
        self.sftp.put(local_path, remote_path)
        self.sftp.close()

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.ssh.close()
        for pid in self.pids_2_kill:
            _stdin, _stdout, _stderr = self.ssh.exec_command('kill {}'.format(pid))
            _stdin, _stdout, _stderr = self.ssh.exec_command('pkill -p {}'.format(pid))


if __name__ == '__main__':

    # SETUP ---------------------------------------------------------

    arg_parser = argparse.ArgumentParser()
    # arg_parser.add_argument('-lf', help='local_file', required=True)
    arg_parser.add_argument('-hs', help='host', required=False)
    arg_parser.add_argument('-u', help='username', required=False)
    arg_parser.add_argument('-p', help='password', required=False)
    args = arg_parser.parse_args()

    host = args.hs
    username = args.u
    password = args.p
    # local_path = args.lf
    local_path = easygui.fileopenbox()

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
    PROGRAM_OUTPUT_FOLDER = '/ccsim/program_outputs'
    BASE_OUTPUT_FOLDER = '/ccsim/xlread_outputs'

    with RemoteInterface(host, username, password) as r_interface:

        # FILE UPLOAD ----------------------------------------------------
        print('Uploading file...')
        _path, filename = os.path.split(local_path)
        # remote_path = LANDING_FOLDER + filename
        remote_path = os.path.join(LANDING_FOLDER, filename)
        r_interface.upload_file(local_path, remote_path)

        # RUN XLSREAD ----------------------------------------------------
        print('Reading file...')
        base_filename, extension = os.path.splitext(filename)
        # xlsread_output_folder = os.path.join(BASE_OUTPUT_FOLDER, base_filename)
        xlsread_output_folder = BASE_OUTPUT_FOLDER + '/' + base_filename
        xlsread_command = '{int} {script} -f {file} -o {output}'.format(int=INTERPRETER_PATH,
                                                                        script=XLSREAD_PATH,
                                                                        file=remote_path,
                                                                        output=xlsread_output_folder)
        r_interface.do_command(xlsread_command, stdout_thru=True)

        # RUN PROGRAM ----------------------------------------------------
        print('Running program...')
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
                                  pro_out=PROGRAM_OUTPUT_FOLDER,
                                  sim_days=32,
                                  gra_days=8,
                                  cut=0.1,
                                  seed=1233232323)

        r_interface.do_command(program_command, pkill_on_exit=True, stdout_thru=True)

        # OUTPUT ----------------------------------------------------
        # todo output


