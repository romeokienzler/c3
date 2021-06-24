#!/usr/bin/env python
# coding: utf-8

# This notebook pulls the HMP accelerometer sensor data classification data set

# In[ ]:


get_ipython().system('pip install pyspark==2.4.4')


# In[ ]:


# @param data_dir temporal data storage for local execution
# @param data_csv csv path and file name (default: data.csv)
# @param data_parquet path and parquet file name (default: data.parquet)
# @param master url of master (default: local mode)


# In[ ]:


from pyspark import SparkContext, SparkConf
from pyspark.sql import SparkSession
import os
from pyspark.sql.types import StructType, StructField, IntegerType
import fnmatch
from pyspark.sql.functions import lit


# In[ ]:


data_csv = os.environ.get('data_csv', 'data.csv')
master = os.environ.get('master', "local[*]")
data_dir = os.environ.get('data_dir', '../../data/')


# Lets create a local spark context (sc) and session (spark)

# In[ ]:


sc = SparkContext.getOrCreate(SparkConf().setMaster(master))

spark = SparkSession     .builder     .getOrCreate()


# Lets pull the data in raw format from the source (github)

# In[ ]:


get_ipython().system('rm -Rf HMP_Dataset')
get_ipython().system('git clone https://github.com/wchill/HMP_Dataset')


# In[ ]:


schema = StructType([
    StructField("x", IntegerType(), True),
    StructField("y", IntegerType(), True),
    StructField("z", IntegerType(), True)])


# This step takes a while, it parses through all files and folders and creates a temporary dataframe for each file which gets appended to an overall data-frame "df". In addition, a column called "class" is added to allow for straightforward usage in Spark afterwards in a supervised machine learning scenario for example.

# In[ ]:


d = 'HMP_Dataset/'

# filter list for all folders containing data (folders that don't start with .)
file_list_filtered = [s for s in os.listdir(d)
                      if os.path.isdir(os.path.join(d, s)) &
                      ~fnmatch.fnmatch(s, '.*')]

# create pandas data frame for all the data

df = None

for category in file_list_filtered:
    data_files = os.listdir('HMP_Dataset/' + category)

    # create a temporary pandas data frame for each data file
    for data_file in data_files:
        print(data_file)
        temp_df = spark.read.             option("header", "false").             option("delimiter", " ").             csv('HMP_Dataset/' + category + '/' + data_file, schema=schema)

        # create a column called "source" storing the current CSV file
        temp_df = temp_df.withColumn("source", lit(data_file))

        # create a column called "class" storing the current data folder
        temp_df = temp_df.withColumn("class", lit(category))

        if df is None:
            df = temp_df
        else:
            df = df.union(temp_df)


# Lets write the dataf-rame to a file in "CSV" format, this will also take quite some time:

# In[ ]:


df.write.option("header", "true").csv(data_dir + data_csv)


# Now we should have a CSV file with our contents
