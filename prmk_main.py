import sys
import time
import json
import select
import paramiko
from time import sleep
import argparse
import os


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


def summon_commands(host, user, password):
    ssh, sftp = _connect(host, user, password)

    def do_command(command_str, stdout_thru=False):
        stdin, stdout, stderr = ssh.exec_command(command_str)
        while not stderr.channel.exit_status_ready():
            if not stdout_thru:
                sleep(0.1)
            else:
                if stderr.channel.recv_ready():
                    rl, wl, xl = select.select([stderr.channel], [], [], 0.0)
                    if len(rl) > 0:
                        # Print data from stdout
                        print(stderr.channel.recv(1024)),

    def upload_file(local_path, remote_path):
        sftp.put(local_path, remote_path)
        sftp.close()

    def close():
        ssh.close()

    return do_command, upload_file, close


# do_command, upload_file, ssh_close = summon_commands(host, user, password)
# do_command('ls', stdout_thru=True)
# upload_file(r"C:\Users\FR\Desktop\culo.txt", "/tmp/prova/culo.txt")
# ssh_close()

if __name__ == '__main__':

    # SETUP ---------------------------------------------------------

    arg_parser = argparse.ArgumentParser()
    arg_parser.add_argument('-lf', help='local_file', required=True)
    arg_parser.add_argument('-hs', help='host', required=False)
    arg_parser.add_argument('-u', help='username', required=False)
    arg_parser.add_argument('-p', help='password', required=False)
    args = arg_parser.parse_args()

    host = args.hs
    username = args.u
    password = args.p
    local_path = args.lf

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

    do_command, upload_file, ssh_close = summon_commands(host, username, password)

    # FILE UPLOAD ----------------------------------------------------
    print('Uploading file...')
    _path, filename = os.path.split(local_path)
    # remote_path = LANDING_FOLDER + filename
    remote_path = os.path.join(LANDING_FOLDER, filename)
    upload_file(local_path, remote_path)

    # RUN XLSREAD ----------------------------------------------------
    print('Reading file...')
    base_filename, extension = os.path.splitext(filename)
    # xlsread_output_folder = os.path.join(BASE_OUTPUT_FOLDER, base_filename)
    xlsread_output_folder = BASE_OUTPUT_FOLDER + '/' + base_filename

    xlsread_command = '{int} {script} -f {file} -o {output}'.format(int=INTERPRETER_PATH,
                                                                    script=XLSREAD_PATH,
                                                                    file=remote_path,
                                                                    output=xlsread_output_folder)

    # print(xlsread_command)
    do_command(xlsread_command, stdout_thru=True)

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

    # print(program_command)
    do_command(program_command, stdout_thru=True)

    # OUTPUT ----------------------------------------------------
    # todo output

    # !!! REMEMBER!!!
    ssh_close()
    # !!! REMEMBER!!!

