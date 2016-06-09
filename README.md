# telegraf_jmx

## jmx stats retriever for telegraf ([influxdata](https://influxdata.com/time-series-platform/telegraf/))

If you cannot use jolokia but you need to retrieve JMX statistics, this is your solution. It uses jython (jython jar included in the repository) to connect to the JMX and retrieve a list of JMX beans. It is a little bit slower to startup, so I suggest to configure the input plugin on telegraf as follow

```
[[inputs.exec]]
    interval = "60s"
    commands = ["/usr/bin/sudo /opt/telegraf_jmx/telegraf_jmx.sh && /bin/cat /tmp/telegraf_jmx.out"]
    timeout = "50s"
    data_format = "influx"
```

You also need to run it as root, so add this line in /etc/sudoers

```
telegraf    ALL=NOPASSWD: /opt/telegraf_jmx/telegraf_jmx.sh
```

The list file for the beans is format as follow:

* fields semicolon separated
* first field: bean domain and name
* second field: bean attribute
* third field: if the bean as a multi value output, a comma separated list of the value name
* comment: # at the beginning of the line
