from javax.management.remote import JMXConnector
from javax.management.remote import JMXConnectorFactory
from javax.management.remote import JMXServiceURL
import logging
import re
import sys
import commands
import logging.handlers

from javax.management import MBeanServerConnection
from javax.management import MBeanInfo
from javax.management import ObjectName
from java.lang import String
from sun.management import ConnectorAddressLink
from jarray import array
from optparse import OptionParser
from javax.management.openmbean import CompositeDataSupport
from javax.management.openmbean import TabularDataSupport
from javax.management import InstanceNotFoundException
from javax.management import AttributeNotFoundException

######## CONFIGURATION SECTION #########
LOG_FILENAME = '/tmp/telegraf_jmx.log'
OUT_FILENAME = '/tmp/telegraf_jmx.out'
JMX_LIST_FILENAME = 'telegraf_jmx.list'
# logging.DEBUG, logging.INFO, logging.WARN, logging.ERROR
LOG_LEVEL = logging.INFO
HOSTNAME = 'cw-stto-oas02'
# comma separated tags to include in telegraf input
ADDITIONAL_TAGS = ''
########################################


logger = logging.getLogger('telegraf_jmx')
logger.setLevel(LOG_LEVEL)
handler = logging.handlers.RotatingFileHandler(LOG_FILENAME, maxBytes=2097152, backupCount=5)
formatter = logging.Formatter('%(asctime)s %(levelname)s %(process)d %(name)s %(module)s.py:%(lineno)d => %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)




def cmd_parser():
    """Parse command line options

    This function parse the command line options:

    * [-s | --server]: JMX ip or dns name
    * [-p | --port]: JMX port
    * [-n | --pid]: Java pid. The script retrieve automatically the JMX url. It could be a comma separated list of pids

    Returns:
        OptionParser: parser instance

    """

    parser = OptionParser()
    parser.add_option('-s', '--server', dest='jmx_server', help="JMX server IP or DNS", default='127.0.0.1')
    parser.add_option('-p', '--port', dest='jmx_port', help="JMX port", default='9999')
    parser.add_option('-n', '--pid', dest='jmx_pid', help="PID of java process (retrieve JMX url automatically). It could be a comma separated list of pids")
    return parser


def get_jmx_url_from_pid(pid):
    """Retrieve JMX URL from process pid

    Args:
        pid(int): pid number of the java process

    Returns:
        str: JMX URL or None if fails

    """

    try:
        url = ConnectorAddressLink.importFrom(pid)
    except:
        logger.error('Cannot retrieve JMX URL from pid: ' + str(pid))
        return None

    return url


def open_jmx_connection(url):
    """Connect to JMX instance

    Args:
        url (str): jmx url to connect to

    Returns:
        jmxConnector: jmx server connection
        MBeanServerConnection: bean server connection

    """

    try:
        jmxServiceUrl = JMXServiceURL(url);
        jmxConnector = JMXConnectorFactory.connect(jmxServiceUrl);
        mBeanServerConnection = jmxConnector.getMBeanServerConnection()
    except Exception, e:
        logger.error('Cannot connect to JMX instance. Error: ' + str(e))
        return None, None

    return jmxConnector, mBeanServerConnection


def close_jmx_connection(jmxConnector):
    """Close a JMX connection

    Args:
        jmxConnector (obj): instance of jmx server connection

    """

    jmxConnector.close()


def get_bean(bean_server, bean, attribute):
    """Retrieve bean attribute from JMX

    Args:
        bean_server (obj): connection to a bean server
        bean (str): domain and name of the bean. Eg: java.lang:type=Memory
        attribute (str): attribute to retrieve. Eg: HeapMemoryUsage

    Returns:
        obj: attribute of the bean
    """

    tmp = None
    objectName = ObjectName(bean);
    try:
        tmp = bean_server.getAttribute(objectName, attribute)
    except Exception, e:
        logger.warn('Cannot retrieve bean attribute. Bean: ' + bean + ' Attribute: ' + attribute + ' Error: ' + str(e))
        return None
    except InstanceNotFoundException, e:
        logger.warn('Cannot retrieve bean attribute. Bean: ' + bean + ' Attribute: ' + attribute + ' Error: ' + str(e))
        return None
    except AttributeNotFoundException, e:
        logger.warn('Cannot retrieve bean attribute. Bean: ' + bean + ' Attribute: ' + attribute + ' Error: ' + str(e))
        return None

    if isinstance(tmp, CompositeDataSupport):
        values = tmp.values()
    elif isinstance(tmp, TabularDataSupport):
        values = tmp.values()
    else:
        values = [tmp]

    return values


def create_jmx_tags(name, bean, attribute, hostname, additional_tags):
    """Create the influxdb tags from the bean name and the attribute

    Args:
        name (str): java virtual machine process name
        bean (str): domain and name of the bean. Eg: java.lang:type=Memory
        attribute (str): attribute to retrieve. Eg: HeapMemoryUsage
        hostname (str): host on which the script runs
        additional_tags (str): additional tags to include in the metric log

    Returns
        str: tags for influxdb. Eg: type=ThreadPool,name=system,domain=oc4j,attr=HeapMemoryUsage

    """

    ret = []
    ret.append('jmx')
    ret.append('jvm_name=' + name)
    ret.append('host=' + hostname)

    m = re.search('[t|T]ype=(.+?)(,|$)', bean)
    if m:
        ret.append('type=' + m.group(1))

    m = re.search('name=(.+?)(,|$)', bean)
    if m:
        ret.append('name=' + m.group(1))

    m = re.search('^(.+?):', bean)
    if m:
        ret.append('domain=' + m.group(1))

    m = re.search('nodeId=(.+?)(,|$)', bean)
    if m:
        ret.append('nodeid=' + m.group(1))

    m = re.search('service=(.+?)(,|$)', bean)
    if m:
        ret.append('service=' + m.group(1))

    ret.append('attr=' + attribute)
    ret.append(additional_tags)

    return ','.join(ret)


if __name__=='__main__':

    parser = cmd_parser()
    (options, args) = parser.parse_args()

    jmx_url = []

    if options.jmx_pid is not None:
        logger.debug('Try to retrieve JMX URL from pid ' + str(options.jmx_pid))
        tmp = options.jmx_pid.split(',')
        for p in tmp:
            jmx_url.append(get_jmx_url_from_pid(int(p)))
    else:
        logger.debug('Retrieve url from command line parameters')
        jmx_url.append('service:jmx:rmi:///jndi/rmi://' + options.jmx_server + ':' + options.jmx_port + '/jmxrmi')

    logger.debug('JMX URL')
    logger.debug(jmx_url)

    fw = open(OUT_FILENAME, 'w')
    
    for url in jmx_url:
        if url is None:
            continue

        jmx_connector, bean_server = open_jmx_connection(url)
        if jmx_connector is None:
            continue

        name = get_bean(bean_server, 'java.lang:type=Runtime', 'Name')
        if name is None:
            logger.error('Cannot retrieve java virtual machine name. Skip this JMX')
            continue
        name = name[0]

        nodeid = get_bean(bean_server, 'Coherence:type=Cluster', 'LocalMemberId')
        if nodeid is not None:
            nodeid = nodeid[0]

        add_tags = ADDITIONAL_TAGS.split(',')
        sysprops = get_bean(bean_server, 'java.lang:type=Runtime', 'SystemProperties')
        for prop in sysprops:
            tmp = prop.values().toArray()
            if tmp[0] == 'tangosol.coherence.role':
                add_tags.append('nc_role=' + tmp[1])
            elif tmp[0] == 'tangosol.coherence.process':
                add_tags.append('nc_process=' + tmp[1])
            elif tmp[0] == 'tangosol.coherence.site':
                add_tags.append('website=' + tmp[1])

        f = open(JMX_LIST_FILENAME, 'r')
        for line in f:
            if line.startswith('#'):
                continue
            map = None
            tmp = line.strip().split(';')
            bean = str(tmp[0])
            attr = str(tmp[1])
            if len(tmp) > 2:
                map = str(tmp[2]).split(',')

            if bean.find('<changeme>') > 0:
                if nodeid is None:
                    continue
                bean = bean.replace('<changeme>', str(nodeid))
            tags = create_jmx_tags(name, bean, attr, HOSTNAME, ','.join(add_tags)[1:])
            values = None
            values = get_bean(bean_server, bean, attr)

            if values is None:
                continue
            elif map is not None:
                i = 0
                for value in values:
                    if type(value) == unicode:
                        value = '"' + str(value) + '"'
                    fw.write(tags + ' ' + map[i] + '=' + str(value) + '\n')
                    i += 1
            else:
                for v in values:
                    if type(v) == unicode:
                        v = '"' + str(v) + '"'
                    fw.write(tags + ' ' + attr + '=' + str(v) + '\n')
        f.close()
        close_jmx_connection(jmx_connector)

    fw.close()


