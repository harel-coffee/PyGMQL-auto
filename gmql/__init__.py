"""
Setting up the pyspark environment
"""
import spylon.spark as ss
import logging
from sys import stdout

c = ss.SparkConfiguration()
c._spark_home = "/home/luca/spark-2.1.0-bin-hadoop2.7"

# I add the GMQL jar files for accessing them from pyspark
c.jars = ["/home/luca/Scrivania/GMQL/GMQL-Core/target/GMQL-Core-2.0.jar",
          "/home/luca/Scrivania/GMQL/GMQL-Server/target/GMQL-Server-2.0.jar",
          "/home/luca/Scrivania/GMQL/GMQL-Spark/target/GMQL-Spark-4.0.jar"]
spark_home = '/home/luca/spark-2.1.0-bin-hadoop2.7'
app_name = 'gmql_spark'
sc = c.spark_context(app_name)

# import findspark
# findspark.init(spark_home=spark_home)
# import pyspark
#
# app_name = 'gmql_spark'
#
# conf = pyspark.SparkConf() \
#     .setMaster('local[*]') \
#     .setAppName(app_name)

"""
    Importing the elements we want to show from outside
"""

from .dataset.GMQLDataset import GMQLDataset
from .dataset import parsers

"""
    GMQL Logger configuration
"""
logger = logging.getLogger('gmql_logger')
logger.setLevel(logging.INFO)

# create a stream handler
handler = logging.StreamHandler(stdout)
handler.setLevel(logging.INFO)

# create a logging format
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)

# add the handlers to the logger
logger.addHandler(handler)
