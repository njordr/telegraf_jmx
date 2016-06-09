#!/bin/bash

BASE_DIR="/root/telegraf_jmx"
JAVA_HOME="/opt/jdk"

cd ${BASE_DIR}
pids=''
for pid in $(ps ax | grep java | awk '{print $1}'); do
    pids="${pids},${pid}"
done
pids=${pids#","}
${JAVA_HOME}/bin/java -jar jython-standalone-2.5.4-rc1.jar telegraf_jmx.py -n ${pids}
