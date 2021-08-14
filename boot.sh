#!/usr/bin/env bash

basedir=$(cd "$(dirname "$0")"; pwd)
cd ${basedir}
. ./venv/bin/activate

function getpid() {
  pid=`pstree -ap|grep gunicorn| grep -v grep| head -n 1| awk -F ',' '{print $2}'| awk '{print $1}'`
}


function start(){
    getpid;
    if [[ ! -z $pid ]];then
        echo "服务已运行中,pid:" $pid
        exit 1;
    fi
    cpu=`cat /proc/cpuinfo| grep "processor"| wc -l`
    ts=`expr $cpu \* 2 + 1`
    
    gunicorn -D -w $ts -b 0.0.0.0:8000 app:app
}

function stop(){
    getpid;
    if [[ ! -z $pid ]];then
        echo "服务已运行中,pid:" $pid
    else
      echo "服务未启动,无需停止."
      exit 1;
    fi
    kill -9 $pid
}

function restart(){
    getpid;
    if [[ ! -z $pid ]];then
        echo "服务已运行中,pid:" $pid
    else
      echo "服务未启动,无需停止."
      start;
      exit 1;
    fi
    kill -HUP $pid
}

function status(){
    getpid;
    if [[ ! -z $pid ]];then
        echo "服务运行中,pid:" $pid
    else
        echo "服务未启动."
        exit 1;
    fi
}

function usage(){
    echo "$0 <start|stop|restart|status>"
}

case $1 in
    start)
       start;
       ;;
    stop)
       stop;
       ;;
    restart)
       restart;
       ;;
    status)
        status;
        ;;
    *)
       usage;
       ;;
esac
