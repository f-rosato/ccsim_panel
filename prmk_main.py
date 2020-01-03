import sys
import time
import select
import paramiko
from time import sleep
import argparse
import os

# host = '173.249.52.100'
# user = 'fede'
# password = 'XvIFkdsj2im8mvg5hB31'

LANDING_FOLDER = '/tmp/landing/'


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
        while not stdout.channel.exit_status_ready():
            if not stdout_thru:
                sleep(0.1)
            else:
                if stdout.channel.recv_ready():
                    rl, wl, xl = select.select([stdout.channel], [], [], 0.0)
                    if len(rl) > 0:
                        # Print data from stdout
                        print(stdout.channel.recv(1024)),

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
    arg_parser = argparse.ArgumentParser()
    arg_parser.add_argument('-hs', help='host', required=True)
    arg_parser.add_argument('-u', help='username', required=True)
    arg_parser.add_argument('-p', help='password', required=True)
    arg_parser.add_argument('-lf', help='local_file', required=True)
    args = arg_parser.parse_args()

    host = args.hs
    user = args.u
    password = args.p
    local_path = args.lf

    do_command, upload_file, ssh_close = summon_commands(host, user, password)
    do_command('ls', stdout_thru=True)
    _path, filename = os.path.split(local_path)
    # remote_path = LANDING_FOLDER + filename
    remote_path = os.path.join(LANDING_FOLDER, filename)
    print(local_path)
    print(remote_path)
    upload_file(local_path, remote_path)

    # todo run xlsread
    # todo run program
    # todo output

    # !!! REMEMBER!!!
    ssh_close()
    # !!! REMEMBER!!!

