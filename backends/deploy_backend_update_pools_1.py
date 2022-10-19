import sys
sys.path.append('../')
from config import Cfg

if __name__ == '__main__':
    cur_path = sys.path[0]
    print("Working Path is:", cur_path)

    network_id = Cfg.NETWORK_ID

    exec_lines = []
    tmpl = open("%s/backend_update_pools_1.sh.tmpl" % cur_path, mode='r')
    while True:
        line = tmpl.readline()
        if not line:
            break
        exec_lines.append(line.replace("[CUR_PATH]", cur_path).replace("[NETWORK_ID]", network_id))
    tmpl.close()

    target_file = open("%s/backend_update_pools_1.sh" % cur_path, mode='w')
    target_file.writelines(exec_lines)
    target_file.close()

    print("Note: backend_update_pools_1.sh should be generated at that Path, ")
    print("please make it excuteable, such as chmod a+x backend_update_pools_1.sh. ")
    print("and then put it into crontab for periodically invoke!")
    print("Crontab eg: ")
    print("  */1 * * * * /working_path/backend_update_pools_1.sh > /dev/null")

