# Fabric notebook source

# METADATA ********************

# META {
# META   "kernel_info": {
# META     "name": "synapse_pyspark"
# META   },
# META   "dependencies": {
# META     "lakehouse": {
# META       "default_lakehouse": "e9b09e4e-b7b9-4208-b9ec-bb3433154555",
# META       "default_lakehouse_name": "lh_enercare_demo",
# META       "default_lakehouse_workspace_id": "b976cac2-7754-4061-88c2-61c0ac016a99"
# META     }
# META   }
# META }

# CELL ********************

# =============================================================================
# nb_01_setup_demo_environment.py
# Fabric Notebook — Cell-by-cell (paste into a Spark notebook in Fabric)
#
# Purpose : Creates the demo lakehouse tables in lh_enercare_demo and populates
#           them with the same sample data as 01_demo_seed_data.sql, but
#           entirely in-memory via PySpark.  No SQL Server connection required.
#
# Run before : nb_02_metadata_pipeline_demo.py
# Prereqs    : Attach this notebook to lh_enercare_demo (default lakehouse)
# =============================================================================


# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# Lakehouse that will hold the demo transactional Delta tables
DEMO_LAKEHOUSE = "lh_enercare_demo"

print(f"Demo lakehouse : {DEMO_LAKEHOUSE}")
print("SparkSession   :", spark.version)


# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

from pyspark.sql import Row
from pyspark.sql.types import *
from datetime import date

products_schema = StructType([
    StructField("product_id",        IntegerType(), False),
    StructField("product_code",      StringType(),  False),
    StructField("product_name",      StringType(),  False),
    StructField("product_category",  StringType(),  False),
    StructField("billing_frequency", StringType(),  False),
    StructField("base_price",        DoubleType(),  False),
    StructField("is_active",         IntegerType(), False),
    StructField("effective_date",    DateType(),    False),
])

products_data = [
    (1,  "WH-GAS-STD",  "Natural Gas Water Heater – Standard Rental",  "Rental",     "Monthly",  24.99, 1, date(2020, 1, 1)),
    (2,  "WH-GAS-PREM", "Natural Gas Water Heater – Premium Rental",   "Rental",     "Monthly",  34.99, 1, date(2020, 1, 1)),
    (3,  "WH-ELEC-STD", "Electric Water Heater – Standard Rental",     "Rental",     "Monthly",  19.99, 1, date(2020, 1, 1)),
    (4,  "PP-HEAT",      "Heating Protection Plus",                     "Protection", "Monthly",  39.99, 1, date(2019, 1, 1)),
    (5,  "PP-COOL",      "Cooling Advantage Plan",                      "Protection", "Monthly",  24.99, 1, date(2019, 1, 1)),
    (6,  "PP-PLUMB",     "Plumbing Protection Plan",                    "Protection", "Monthly",  14.99, 1, date(2019, 1, 1)),
    (7,  "PP-ELEC-HM",   "Electrical Home Protection",                  "Protection", "Monthly",  19.99, 1, date(2021, 6, 1)),
    (8,  "SH-BASIC",     "Smart Home Essentials",                       "SmartHome",  "Monthly",  29.99, 1, date(2022, 1, 1)),
    (9,  "SH-PREM",      "Smart Home Premium",                          "SmartHome",  "Monthly",  59.99, 1, date(2022, 1, 1)),
    (10, "ECOBEE-INST",  "ecobee Smart Thermostat – Supply & Install",  "SmartHome",  "OneTime", 249.00, 1, date(2022, 3, 1)),
]

df_products = spark.createDataFrame(products_data, schema=products_schema)
df_products.write.format("delta").mode("overwrite").saveAsTable(f"{DEMO_LAKEHOUSE}.products")
print(f"  products: {df_products.count()} rows written")


# ---------------------------------------------------------------------------
# CELL 3 — Customers (50 rows — Ontario residential + commercial + MUR)
# Postal codes: Statistics Canada Ontario FSAs
# ---------------------------------------------------------------------------
customers_schema = StructType([
    StructField("customer_id",        IntegerType(), False),
    StructField("account_number",     StringType(),  False),
    StructField("first_name",         StringType(),  True),
    StructField("last_name",          StringType(),  True),
    StructField("email",              StringType(),  True),
    StructField("phone",              StringType(),  True),
    StructField("customer_type",      StringType(),  False),
    StructField("status",             StringType(),  False),
    StructField("city",               StringType(),  True),
    StructField("province",           StringType(),  False),
    StructField("postal_code",        StringType(),  True),
    StructField("created_date",       DateType(),    False),
])

customers_data = [
    # id, account_number, first, last, email, phone, type, status, city, prov, postal, created
    (1,  "EC-0001001","James",    "Whitmore",   "j.whitmore@email.ca",       "416-555-0101","Residential","Active",  "Toronto",        "ON","M4K 1A1",date(2018,3,15)),
    (2,  "EC-0001002","Sophie",   "Tremblay",   "stremblay@outlook.com",     "416-555-0102","Residential","Active",  "Toronto",        "ON","M6G 3H2",date(2019,6,20)),
    (3,  "EC-0001003","Raj",      "Patel",      "rajpatel@gmail.com",        "905-555-0103","Residential","Active",  "Mississauga",    "ON","L5B 2C4",date(2017,11,8)),
    (4,  "EC-0001004","Mei",      "Chen",       "mei.chen@hotmail.com",      "905-555-0104","Residential","Active",  "Markham",        "ON","L3R 4G5",date(2020,2,14)),
    (5,  "EC-0001005","Patrick",  "OBrien",     "pobrien@rogers.ca",         "416-555-0105","Residential","Active",  "Etobicoke",      "ON","M9C 2A1",date(2016,8,22)),
    (6,  "EC-0001006","Amara",    "Okafor",     "amara.okafor@gmail.com",    "647-555-0106","Residential","Active",  "Toronto",        "ON","M1B 3W2",date(2021,5,10)),
    (7,  "EC-0001007","Yuki",     "Nakamura",   "yukinaka@yahoo.ca",         "905-555-0107","Residential","Active",  "Oakville",       "ON","L6H 5N3",date(2019,9,3)),
    (8,  "EC-0001008","Carlos",   "Morales",    "carlos.m@gmail.com",        "905-555-0108","Residential","Active",  "Brampton",       "ON","L6Y 4K8",date(2020,7,17)),
    (9,  "EC-0001009","Diana",    "Leclair",    "dleclair@sympatico.ca",     "613-555-0109","Residential","Active",  "Ottawa",         "ON","K1S 5B6",date(2018,1,30)),
    (10, "EC-0001010","Samuel",   "Wright",     "samwright@live.ca",         "905-555-0110","Residential","Active",  "Hamilton",       "ON","L8S 2J9",date(2015,4,12)),
    (11, "EC-0001011","Fatima",   "Al-Rashid",  "f.alrashid@bell.net",       "416-555-0111","Residential","Active",  "Scarborough",    "ON","M1P 2V7",date(2022,3,8)),
    (12, "EC-0001012","Andrew",   "MacLeod",    "amacleod@cogeco.ca",        "905-555-0112","Residential","Active",  "Burlington",     "ON","L7R 3N2",date(2017,7,25)),
    (13, "EC-0001013","Priya",    "Sharma",     "priya.sharma@gmail.com",    "905-555-0113","Residential","Active",  "Mississauga",    "ON","L5M 6K4",date(2021,11,14)),
    (14, "EC-0001014","Thomas",   "Beaulieu",   "tbeaulieu@videotron.ca",    "613-555-0114","Residential","Active",  "Kanata",         "ON","K2K 1X4",date(2016,12,5)),
    (15, "EC-0001015","Grace",    "Kim",        "gracekim@naver.com",        "416-555-0115","Residential","Active",  "North York",     "ON","M2N 5P2",date(2023,1,19)),
    (16, "EC-0001016","Michael",  "Dupont",     "mdupont@gmail.com",         "613-555-0116","Residential","Active",  "Orleans",        "ON","K4A 3T6",date(2019,8,11)),
    (17, "EC-0001017","Sandra",   "Nielsen",    "snielsen@outlook.com",      "905-555-0117","Residential","Active",  "Ajax",           "ON","L1Z 1N3",date(2020,10,29)),
    (18, "EC-0001018","Kwame",    "Asante",     "kwame.asante@hotmail.com",  "416-555-0118","Residential","Active",  "Toronto",        "ON","M3H 4B7",date(2018,6,3)),
    (19, "EC-0001019","Isabelle", "Gagnon",     "igagnon@bell.ca",           "613-555-0119","Residential","Active",  "Ottawa",         "ON","K2B 7W3",date(2017,3,21)),
    (20, "EC-0001020","Robert",   "Tanaka",     "rtanaka@gmail.com",         "905-555-0120","Residential","Active",  "Oshawa",         "ON","L1H 3Z2",date(2015,9,14)),
    (21, "EC-0001021","Nadia",    "Kowalski",   "nkowalski@rogers.ca",       "416-555-0121","Residential","Inactive","Etobicoke",      "ON","M9W 1P4",date(2014,2,7)),
    (22, "EC-0001022","Ivan",     "Petrov",     "ipetrov@live.com",          "905-555-0122","Residential","Active",  "Whitby",         "ON","L1N 5T8",date(2021,4,16)),
    (23, "EC-0001023","Helene",   "Bouchard",   "hbouchard@laposte.net",     "613-555-0123","Residential","Active",  "Gatineau",       "ON","J8Y 1T4",date(2022,8,30)),
    (24, "EC-0001024","Marcus",   "Thompson",   "m.thompson@gmail.com",      "647-555-0124","Residential","Active",  "Vaughan",        "ON","L4L 8B3",date(2019,12,12)),
    (25, "EC-0001025","Lin",      "Zhang",      "lin.zhang@yahoo.ca",        "905-555-0125","Residential","Active",  "Richmond Hill",  "ON","L4C 9K5",date(2020,5,7)),
    (26, "EC-0001026","Olivia",   "Murphy",     "omurphy@cogeco.ca",         "905-555-0126","Residential","Active",  "Kingston",       "ON","K7L 4V2",date(2016,7,18)),
    (27, "EC-0001027","Hassan",   "Ibrahim",    "hibrahim@hotmail.ca",       "416-555-0127","Residential","Active",  "Scarborough",    "ON","M1T 3N6",date(2023,3,22)),
    (28, "EC-0001028","Claire",   "Fontaine",   "cfontaine@sympatico.ca",    "519-555-0128","Residential","Active",  "London",         "ON","N6A 4C9",date(2018,10,1)),
    (29, "EC-0001029","Derek",    "Sinclair",   "dsinclair@bell.net",        "905-555-0129","Residential","Active",  "Barrie",         "ON","L4N 7P3",date(2017,5,14)),
    (30, "EC-0001030","Yolanda",  "Santos",     "ysantos@rogers.ca",         "416-555-0130","Residential","Active",  "Toronto",        "ON","M6R 1E8",date(2021,7,9)),
    (31, "EC-0001031","Nathan",   "Bergeron",   "nbergeron@videotron.ca",    "613-555-0131","Residential","Active",  "Ottawa",         "ON","K1V 9B4",date(2019,2,25)),
    (32, "EC-0001032","Anita",    "Verma",      "averma@gmail.com",          "905-555-0132","Residential","Active",  "Mississauga",    "ON","L4Z 3C7",date(2022,1,17)),
    (33, "EC-0001033","Scott",    "Henderson",  "shenderson@outlook.com",    "905-555-0133","Residential","Active",  "Newmarket",      "ON","L3Y 8C2",date(2016,4,3)),
    (34, "EC-0001034","Zara",     "Ali",        "zali@hotmail.com",          "416-555-0134","Residential","Active",  "North York",     "ON","M2M 2T9",date(2020,11,11)),
    (35, "EC-0001035","Eric",     "Larochelle", "elarochelle@bell.ca",       "613-555-0135","Residential","Active",  "Ottawa",         "ON","K2P 1T3",date(2018,8,27)),
    (36, "EC-0001036","Vanessa",  "Castillo",   "vcastillo@gmail.com",       "905-555-0136","Residential","Active",  "Pickering",      "ON","L1V 3X9",date(2021,9,5)),
    (37, "EC-0001037","Brendan",  "Walsh",      "bwalsh@rogers.ca",          "519-555-0137","Residential","Active",  "Guelph",         "ON","N1G 5A8",date(2017,1,23)),
    (38, "EC-0001038","Mei-Ling", "Lau",        "meilau@yahoo.ca",           "905-555-0138","Residential","Active",  "Markham",        "ON","L3S 4K2",date(2019,7,14)),
    (39, "EC-0001039","Jerome",   "Fontaine",   "jfontaine@cogeco.ca",       "613-555-0139","Residential","Active",  "Ottawa",         "ON","K2H 8P7",date(2020,3,30)),
    (40, "EC-0001040","Angela",   "Kowalczyk",  "akowalczyk@gmail.com",      "416-555-0140","Residential","Active",  "Toronto",        "ON","M5V 2H1",date(2022,6,15)),
    # Commercial
    (41, "EC-0002001","Maple Leaf Properties",  None, "accounts@mlproperties.ca",    "416-555-0201","Commercial","Active","Toronto",    "ON","M5H 2N2",date(2015,11,1)),
    (42, "EC-0002002","Sunrise Plazas Inc",     None, "facilities@sunriseplazas.ca", "905-555-0202","Commercial","Active","Mississauga", "ON","L4W 1S9",date(2016,3,14)),
    (43, "EC-0002003","Lakeview Medical Centre",None, "admin@lakeviewmed.ca",        "905-555-0203","Commercial","Active","Burlington",  "ON","L7L 6A4",date(2017,9,22)),
    (44, "EC-0002004","Cornerstone Realty",     None, "info@cstonerealty.ca",        "613-555-0204","Commercial","Active","Ottawa",      "ON","K1G 4K3",date(2018,5,16)),
    (45, "EC-0002005","Northgate Logistics",    None, "ops@northgatelogis.ca",       "905-555-0205","Commercial","Active","Brampton",    "ON","L6T 5A9",date(2019,10,7)),
    # MUR
    (46, "EC-0003001","Harbourview Condos",     None, "manager@hvcondos.ca",         "416-555-0301","MUR",       "Active","Toronto",    "ON","M5J 2T3",date(2016,6,1)),
    (47, "EC-0003002","Riverside Gardens",      None, "super@riversidegardens.ca",   "613-555-0302","MUR",       "Active","Ottawa",     "ON","K1K 2Z8",date(2017,2,28)),
    (48, "EC-0003003","Oakwood Manor Rentals",  None, "office@oakwoodmanor.ca",      "905-555-0303","MUR",       "Active","Hamilton",   "ON","L8P 4V7",date(2018,7,19)),
    (49, "EC-0003004","Greenfield Residences",  None, "mgmt@greenfieldres.ca",       "905-555-0304","MUR",       "Active","Markham",    "ON","L3R 0J4",date(2020,1,15)),
    (50, "EC-0003005","Skyline Towers",         None, "admin@skylinetowers.ca",       "416-555-0305","MUR",       "Active","North York", "ON","M2J 1L8",date(2021,3,10)),
]

df_customers = spark.createDataFrame(customers_data, schema=customers_schema)
df_customers.write.format("delta").mode("overwrite").saveAsTable(f"{DEMO_LAKEHOUSE}.customers")
print(f"  customers: {df_customers.count()} rows written")


# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

sa_schema = StructType([
    StructField("service_account_id",  IntegerType(), False),
    StructField("customer_id",         IntegerType(), False),
    StructField("account_number",      StringType(),  False),
    StructField("utility_type",        StringType(),  False),
    StructField("rate_class",          StringType(),  True),
    StructField("distributor",         StringType(),  True),
    StructField("status",              StringType(),  False),
    StructField("service_address",     StringType(),  True),
    StructField("city",                StringType(),  True),
    StructField("postal_code",         StringType(),  True),
    StructField("opened_date",         DateType(),    False),
])

sa_data = [
    # (sa_id, cust_id, acct_no, utility, rate_class, distributor, status, address, city, postal, opened)
    (1,  1,  "SA-1001-GAS",  "Natural Gas",  "Residential",        "Enbridge Gas", "Active","142 Broadview Ave",     "Toronto",       "M4K 1A1",date(2018,3,15)),
    (2,  1,  "SA-1001-WH",   "Water Heater", "Residential",        "Enbridge Gas", "Active","142 Broadview Ave",     "Toronto",       "M4K 1A1",date(2018,3,15)),
    (3,  2,  "SA-1002-GAS",  "Natural Gas",  "Residential",        "Enbridge Gas", "Active","87 Christie St",        "Toronto",       "M6G 3H2",date(2019,6,20)),
    (4,  3,  "SA-1003-GAS",  "Natural Gas",  "Residential",        "Enbridge Gas", "Active","3245 Hurontario St",    "Mississauga",   "L5B 2C4",date(2017,11,8)),
    (5,  3,  "SA-1003-COOL", "HVAC",         "Residential",        "Enbridge Gas", "Active","3245 Hurontario St",    "Mississauga",   "L5B 2C4",date(2019,5,1)),
    (6,  4,  "SA-1004-GAS",  "Natural Gas",  "Residential",        "Enbridge Gas", "Active","74 Warden Ave",         "Markham",       "L3R 4G5",date(2020,2,14)),
    (7,  5,  "SA-1005-GAS",  "Natural Gas",  "Residential",        "Enbridge Gas", "Active","1891 Kipling Ave",      "Etobicoke",     "M9C 2A1",date(2016,8,22)),
    (8,  5,  "SA-1005-WH",   "Water Heater", "Residential",        "Enbridge Gas", "Active","1891 Kipling Ave",      "Etobicoke",     "M9C 2A1",date(2016,8,22)),
    (9,  6,  "SA-1006-GAS",  "Natural Gas",  "Residential",        "Enbridge Gas", "Active","28 Morningside Ave",    "Scarborough",   "M1B 3W2",date(2021,5,10)),
    (10, 7,  "SA-1007-GAS",  "Natural Gas",  "Residential",        "Enbridge Gas", "Active","512 Trafalgar Rd",      "Oakville",      "L6H 5N3",date(2019,9,3)),
    (11, 7,  "SA-1007-COOL", "HVAC",         "Residential",        "Enbridge Gas", "Active","512 Trafalgar Rd",      "Oakville",      "L6H 5N3",date(2021,6,15)),
    (12, 8,  "SA-1008-GAS",  "Natural Gas",  "Residential",        "Enbridge Gas", "Active","88 Sandalwood Pkwy",    "Brampton",      "L6Y 4K8",date(2020,7,17)),
    (13, 9,  "SA-1009-GAS",  "Natural Gas",  "Residential",        "Enbridge Gas", "Active","220 Glebe Ave",         "Ottawa",        "K1S 5B6",date(2018,1,30)),
    (14, 10, "SA-1010-GAS",  "Natural Gas",  "Residential",        "Enbridge Gas", "Active","55 Garth St",           "Hamilton",      "L8S 2J9",date(2015,4,12)),
    (15, 10, "SA-1010-WH",   "Water Heater", "Residential",        "Enbridge Gas", "Active","55 Garth St",           "Hamilton",      "L8S 2J9",date(2015,4,12)),
    (16, 11, "SA-1011-GAS",  "Natural Gas",  "Residential",        "Enbridge Gas", "Active","95 Ellesmere Rd",       "Scarborough",   "M1P 2V7",date(2022,3,8)),
    (17, 12, "SA-1012-GAS",  "Natural Gas",  "Residential",        "Enbridge Gas", "Active","781 Plains Rd E",       "Burlington",    "L7R 3N2",date(2017,7,25)),
    (18, 12, "SA-1012-COOL", "HVAC",         "Residential",        "Enbridge Gas", "Active","781 Plains Rd E",       "Burlington",    "L7R 3N2",date(2020,4,1)),
    (19, 13, "SA-1013-GAS",  "Natural Gas",  "Residential",        "Enbridge Gas", "Active","4060 Creditview Rd",    "Mississauga",   "L5M 6K4",date(2021,11,14)),
    (20, 14, "SA-1014-GAS",  "Natural Gas",  "Residential",        "Enbridge Gas", "Active","98 Hazeldean Rd",       "Kanata",        "K2K 1X4",date(2016,12,5)),
    (21, 15, "SA-1015-ELEC", "Electricity",  "Residential",        "Hydro One",    "Active","310 Sheppard Ave E",    "North York",    "M2N 5P2",date(2023,1,19)),
    (22, 16, "SA-1016-GAS",  "Natural Gas",  "Residential",        "Enbridge Gas", "Active","2150 Tenth Line Rd",    "Orleans",       "K4A 3T6",date(2019,8,11)),
    (23, 17, "SA-1017-GAS",  "Natural Gas",  "Residential",        "Enbridge Gas", "Active","35 Rossland Rd W",      "Ajax",          "L1Z 1N3",date(2020,10,29)),
    (24, 18, "SA-1018-GAS",  "Natural Gas",  "Residential",        "Enbridge Gas", "Active","67 Viewmount Ave",      "Toronto",       "M3H 4B7",date(2018,6,3)),
    (25, 19, "SA-1019-GAS",  "Natural Gas",  "Residential",        "Enbridge Gas", "Active","440 Woodroffe Ave",     "Ottawa",        "K2B 7W3",date(2017,3,21)),
    (26, 20, "SA-1020-GAS",  "Natural Gas",  "Residential",        "Enbridge Gas", "Active","219 Simcoe St S",       "Oshawa",        "L1H 3Z2",date(2015,9,14)),
    (27, 21, "SA-1021-GAS",  "Natural Gas",  "Residential",        "Enbridge Gas", "Closed","40 Burnhamthorpe Rd",   "Etobicoke",     "M9W 1P4",date(2014,2,7)),
    (28, 22, "SA-1022-GAS",  "Natural Gas",  "Residential",        "Enbridge Gas", "Active","110 Brock St N",        "Whitby",        "L1N 5T8",date(2021,4,16)),
    (29, 23, "SA-1023-GAS",  "Natural Gas",  "Residential",        "Enbridge Gas", "Active","355 Principale St",     "Gatineau",      "J8Y 1T4",date(2022,8,30)),
    (30, 24, "SA-1024-GAS",  "Natural Gas",  "Residential",        "Enbridge Gas", "Active","9820 Keele St",         "Vaughan",       "L4L 8B3",date(2019,12,12)),
    (31, 25, "SA-1025-GAS",  "Natural Gas",  "Residential",        "Enbridge Gas", "Active","300 Major Mackenzie W", "Richmond Hill", "L4C 9K5",date(2020,5,7)),
    (32, 26, "SA-1026-GAS",  "Natural Gas",  "Residential",        "Enbridge Gas", "Active","88 Princess St",        "Kingston",      "K7L 4V2",date(2016,7,18)),
    (33, 27, "SA-1027-GAS",  "Natural Gas",  "Residential",        "Enbridge Gas", "Active","55 Pharmacy Ave",       "Scarborough",   "M1T 3N6",date(2023,3,22)),
    (34, 28, "SA-1028-GAS",  "Natural Gas",  "Residential",        "Union Gas",    "Active","745 Wellington Rd S",   "London",        "N6A 4C9",date(2018,10,1)),
    (35, 29, "SA-1029-GAS",  "Natural Gas",  "Residential",        "Enbridge Gas", "Active","430 Mapleview Dr W",    "Barrie",        "L4N 7P3",date(2017,5,14)),
    (36, 30, "SA-1030-GAS",  "Natural Gas",  "Residential",        "Enbridge Gas", "Active","1180 Bloor St W",       "Toronto",       "M6R 1E8",date(2021,7,9)),
    (37, 31, "SA-1031-GAS",  "Natural Gas",  "Residential",        "Enbridge Gas", "Active","1465 Merivale Rd",      "Ottawa",        "K1V 9B4",date(2019,2,25)),
    (38, 32, "SA-1032-GAS",  "Natural Gas",  "Residential",        "Enbridge Gas", "Active","900 Rathburn Rd W",     "Mississauga",   "L4Z 3C7",date(2022,1,17)),
    (39, 33, "SA-1033-GAS",  "Natural Gas",  "Residential",        "Enbridge Gas", "Active","17555 Yonge St",        "Newmarket",     "L3Y 8C2",date(2016,4,3)),
    (40, 34, "SA-1034-GAS",  "Natural Gas",  "Residential",        "Enbridge Gas", "Active","4100 Bathurst St",      "North York",    "M2M 2T9",date(2020,11,11)),
    (41, 35, "SA-1035-GAS",  "Natural Gas",  "Residential",        "Enbridge Gas", "Active","230 Elgin St",          "Ottawa",        "K2P 1T3",date(2018,8,27)),
    (42, 36, "SA-1036-GAS",  "Natural Gas",  "Residential",        "Enbridge Gas", "Active","1215 Kingston Rd",      "Pickering",     "L1V 3X9",date(2021,9,5)),
    (43, 37, "SA-1037-GAS",  "Natural Gas",  "Residential",        "Union Gas",    "Active","99 Stone Rd W",         "Guelph",        "N1G 5A8",date(2017,1,23)),
    (44, 38, "SA-1038-GAS",  "Natural Gas",  "Residential",        "Enbridge Gas", "Active","7700 Kennedy Rd",       "Markham",       "L3S 4K2",date(2019,7,14)),
    (45, 39, "SA-1039-GAS",  "Natural Gas",  "Residential",        "Enbridge Gas", "Active","1547 Woodward Dr",      "Ottawa",        "K2H 8P7",date(2020,3,30)),
    (46, 40, "SA-1040-GAS",  "Natural Gas",  "Residential",        "Enbridge Gas", "Active","555 King St W",         "Toronto",       "M5V 2H1",date(2022,6,15)),
    # Commercial
    (47, 41, "SA-2001-COM",  "Natural Gas",  "General Commercial", "Enbridge Gas", "Active","100 King St W Ste 800", "Toronto",       "M5H 2N2",date(2015,11,1)),
    (48, 42, "SA-2002-COM",  "Natural Gas",  "General Commercial", "Enbridge Gas", "Active","5800 Dixie Rd",         "Mississauga",   "L4W 1S9",date(2016,3,14)),
    (49, 43, "SA-2003-COM",  "Natural Gas",  "General Commercial", "Enbridge Gas", "Active","3200 Harvester Rd",     "Burlington",    "L7L 6A4",date(2017,9,22)),
    (50, 44, "SA-2004-COM",  "Natural Gas",  "General Commercial", "Enbridge Gas", "Active","280 Slater St",         "Ottawa",        "K1G 4K3",date(2018,5,16)),
    (51, 45, "SA-2005-COM",  "Natural Gas",  "General Commercial", "Enbridge Gas", "Active","10 Parkhurst Dr",       "Brampton",      "L6T 5A9",date(2019,10,7)),
    # MUR
    (52, 46, "SA-3001-MUR",  "Natural Gas",  "Residential",        "Enbridge Gas", "Active","300 Queens Quay W",     "Toronto",       "M5J 2T3",date(2016,6,1)),
    (53, 47, "SA-3002-MUR",  "Natural Gas",  "Residential",        "Enbridge Gas", "Active","200 Tremblay Rd",       "Ottawa",        "K1K 2Z8",date(2017,2,28)),
    (54, 48, "SA-3003-MUR",  "Natural Gas",  "Residential",        "Enbridge Gas", "Active","112 James St N",        "Hamilton",      "L8P 4V7",date(2018,7,19)),
    (55, 49, "SA-3004-MUR",  "Natural Gas",  "Residential",        "Enbridge Gas", "Active","9800 McCowan Rd",       "Markham",       "L3R 0J4",date(2020,1,15)),
    (56, 50, "SA-3005-MUR",  "Natural Gas",  "Residential",        "Enbridge Gas", "Active","4789 Yonge St",         "North York",    "M2J 1L8",date(2021,3,10)),
]

df_sa = spark.createDataFrame(sa_data, schema=sa_schema)
df_sa.write.format("delta").mode("overwrite").saveAsTable(f"{DEMO_LAKEHOUSE}.service_accounts")
print(f"  service_accounts: {df_sa.count()} rows written")


# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

equip_schema = StructType([
    StructField("equipment_id",      IntegerType(), False),
    StructField("service_account_id",IntegerType(), False),
    StructField("equipment_type",    StringType(),  False),
    StructField("make",              StringType(),  True),
    StructField("model",             StringType(),  True),
    StructField("serial_number",     StringType(),  True),
    StructField("ownership_type",    StringType(),  False),
    StructField("fuel_type",         StringType(),  True),
    StructField("install_date",      DateType(),    True),
    StructField("warranty_expiry",   DateType(),    True),
    StructField("status",            StringType(),  False),
])

# sa_id lookup by account_number from the sa_data list above
sa_id_map = {row[2]: row[0] for row in sa_data}

equip_raw = [
    # (eq_id, acct_no, type, make, model, serial, ownership, fuel, install, warranty, status)
    (1,  "SA-1001-WH",  "Water Heater",    "Rheem",          "Performance Plus 40G",      "RH2019-041847","Rental",         "Natural Gas","2019-03-22","2024-03-22","Active"),
    (2,  "SA-1005-WH",  "Water Heater",    "Bradford White", "RG250H6-1",                 "BW2016-088231","Rental",         "Natural Gas","2016-09-14","2021-09-14","Active"),
    (3,  "SA-1010-WH",  "Water Heater",    "A.O. Smith",     "ProMax 50G",                "AO2015-059944","Rental",         "Natural Gas","2015-05-20","2020-05-20","Active"),
    (4,  "SA-1001-GAS", "Furnace",         "Lennox",         "EL296V",                    "LX2018-112034","Customer-Owned", "Natural Gas","2018-11-05","2028-11-05","Active"),
    (5,  "SA-1003-GAS", "Furnace",         "Carrier",        "Performance 96",            "CR2017-203811","Customer-Owned", "Natural Gas","2017-12-10","2027-12-10","Active"),
    (6,  "SA-1005-GAS", "Furnace",         "York",           "TM9V",                      "YK2016-094520","Customer-Owned", "Natural Gas","2016-10-03","2026-10-03","Active"),
    (7,  "SA-1007-GAS", "Furnace",         "Goodman",        "GMSS960603BN",              "GD2019-187623","Customer-Owned", "Natural Gas","2019-10-17","2024-10-17","Active"),
    (8,  "SA-1009-GAS", "Furnace",         "Lennox",         "SLP99V",                    "LX2018-208410","Customer-Owned", "Natural Gas","2018-02-14","2028-02-14","Active"),
    (9,  "SA-1010-GAS", "Furnace",         "Carrier",        "Infinity 98",               "CR2015-094017","Customer-Owned", "Natural Gas","2015-06-08","2025-06-08","Active"),
    (10, "SA-1012-GAS", "Furnace",         "Lennox",         "ML296V",                    "LX2017-301755","Customer-Owned", "Natural Gas","2017-08-22","2022-08-22","Active"),
    (11, "SA-1014-GAS", "Furnace",         "York",           "YP9C",                      "YK2016-204319","Customer-Owned", "Natural Gas","2016-12-30","2021-12-30","Active"),
    (12, "SA-1016-GAS", "Furnace",         "Goodman",        "GCVC960604CX",              "GD2019-394812","Customer-Owned", "Natural Gas","2019-09-01","2024-09-01","Active"),
    (13, "SA-1020-GAS", "Furnace",         "Lennox",         "EL296V",                    "LX2015-105522","Customer-Owned", "Natural Gas","2015-10-15","2020-10-15","Active"),
    (14, "SA-1001-GAS", "Central AC",      "Lennox",         "XC21",                      "LX2018-AC4420","Customer-Owned", "Electric",   "2018-06-01","2028-06-01","Active"),
    (15, "SA-1003-COOL","Central AC",      "Carrier",        "Infinity 21",               "CR2019-AC8811","Customer-Owned", "Electric",   "2019-05-15","2029-05-15","Active"),
    (16, "SA-1005-GAS", "Central AC",      "York",           "YXV",                       "YK2016-AC3120","Customer-Owned", "Electric",   "2016-05-28","2026-05-28","Active"),
    (17, "SA-1007-COOL","Central AC",      "Lennox",         "SCA060H4B",                 "LX2021-AC9920","Customer-Owned", "Electric",   "2021-06-20","2031-06-20","Active"),
    (18, "SA-1012-COOL","Central AC",      "Goodman",        "GSX140481",                 "GD2020-AC7741","Customer-Owned", "Electric",   "2020-05-10","2025-05-10","Active"),
    (19, "SA-1015-ELEC","Heat Pump",       "Carrier",        "Infinity 20 GREENSPEED",    "CR2023-HP0041","Customer-Owned", "Electric",   "2023-02-10","2033-02-10","Active"),
    (20, "SA-1040-GAS", "Heat Pump",       "Lennox",         "XP25",                      "LX2022-HP8811","Customer-Owned", "Electric",   "2022-07-18","2032-07-18","Active"),
    (21, "SA-1001-GAS", "Smart Thermostat","ecobee",         "SmartThermostat Premium",   "EB2022-TH3341","Customer-Owned", None,         "2022-04-05","2027-04-05","Active"),
    (22, "SA-1003-GAS", "Smart Thermostat","ecobee",         "SmartThermostat Enhanced",  "EB2021-TH1192","Customer-Owned", None,         "2021-09-12","2026-09-12","Active"),
    (23, "SA-1007-GAS", "Smart Thermostat","Honeywell Home", "T9 Smart Thermostat",       "HW2020-TH5512","Customer-Owned", None,         "2020-11-03","2025-11-03","Active"),
    (24, "SA-1009-GAS", "Smart Thermostat","ecobee",         "SmartThermostat Premium",   "EB2023-TH8871","Customer-Owned", None,         "2023-01-28","2028-01-28","Active"),
    (25, "SA-1012-GAS", "Smart Thermostat","Honeywell Home", "T6 Pro Smart Thermostat",   "HW2019-TH2219","Customer-Owned", None,         "2019-11-15","2024-11-15","Active"),
    (26, "SA-3001-MUR", "Water Heater",    "Rheem",          "Marathon 85G Electric",     "RH2016-MUR001","Rental",         "Electric",   "2016-07-15","2021-07-15","Active"),
    (27, "SA-3001-MUR", "Furnace",         "Carrier",        "Performance 80",            "CR2016-MUR002","Rental",         "Natural Gas","2016-07-15","2026-07-15","Active"),
    (28, "SA-3002-MUR", "Water Heater",    "Bradford White", "RE280T6-1NCWW",             "BW2017-MUR001","Rental",         "Electric",   "2017-03-10","2022-03-10","Active"),
    (29, "SA-3002-MUR", "Furnace",         "Lennox",         "ML296V",                    "LX2017-MUR002","Rental",         "Natural Gas","2017-03-10","2027-03-10","Active"),
    (30, "SA-3003-MUR", "Water Heater",    "A.O. Smith",     "PROMO 50",                  "AO2018-MUR001","Rental",         "Natural Gas","2018-08-20","2023-08-20","Active"),
    (31, "SA-3004-MUR", "Water Heater",    "Rheem",          "Classic 50G",               "RH2020-MUR001","Rental",         "Natural Gas","2020-02-05","2025-02-05","Active"),
    (32, "SA-3005-MUR", "Water Heater",    "Bradford White", "RG240H6-1",                 "BW2021-MUR001","Rental",         "Natural Gas","2021-04-01","2026-04-01","Active"),
    (33, "SA-3005-MUR", "Central AC",      "York",           "YZV",                       "YK2021-MUR002","Rental",         "Electric",   "2021-05-12","2031-05-12","Active"),
    (34, "SA-2001-COM", "Water Heater",    "Rheem",          "Commercial 100G Gas",       "RH2015-COM001","Rental",         "Natural Gas","2015-11-15","2020-11-15","Active"),
    (35, "SA-2002-COM", "Furnace",         "Carrier",        "ComfortHeat 48SS",          "CR2016-COM001","Customer-Owned", "Natural Gas","2016-04-01","2026-04-01","Active"),
    (36, "SA-2003-COM", "Water Heater",    "A.O. Smith",     "ProLine 80G",               "AO2017-COM001","Rental",         "Natural Gas","2017-10-10","2022-10-10","Active"),
    (37, "SA-2004-COM", "Furnace",         "Lennox",         "LCH240H4B",                 "LX2018-COM001","Customer-Owned", "Natural Gas","2018-06-01","2028-06-01","Active"),
    (38, "SA-2005-COM", "Water Heater",    "Bradford White", "MI50L6-1NCWWL",             "BW2019-COM001","Rental",         "Natural Gas","2019-10-20","2024-10-20","Active"),
]

from datetime import datetime
equip_data = [
    (row[0], sa_id_map[row[1]], row[2], row[3], row[4], row[5], row[6], row[7],
     date(*[int(x) for x in row[8].split("-")]) if row[8] else None,
     date(*[int(x) for x in row[9].split("-")]) if row[9] else None,
     row[10])
    for row in equip_raw
]

df_equipment = spark.createDataFrame(equip_data, schema=equip_schema)
df_equipment.write.format("delta").mode("overwrite").saveAsTable(f"{DEMO_LAKEHOUSE}.equipment_registry")
print(f"  equipment_registry: {df_equipment.count()} rows written")


# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

print("\n=== Row counts ===")
for tbl in ["customers", "service_accounts", "products", "equipment_registry"]:
    n = spark.table(f"{DEMO_LAKEHOUSE}.{tbl}").count()
    print(f"  {tbl:<25} {n:>5} rows")

print("\nBase tables ready.  Running contracts, service_requests, billing_transactions...\n")


# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

from pyspark.sql.types import *
from datetime import date

product_code_map = {row[1]: row[0] for row in products_data}

contracts_schema = StructType([
    StructField("contract_id",         IntegerType(), False),
    StructField("service_account_id",  IntegerType(), False),
    StructField("product_id",          IntegerType(), False),
    StructField("contract_status",     StringType(),  False),
    StructField("start_date",          DateType(),    False),
    StructField("end_date",            DateType(),    True),
    StructField("monthly_amount",      DoubleType(),  False),
    StructField("auto_renew",          IntegerType(), False),
    StructField("cancellation_date",   DateType(),    True),
    StructField("cancellation_reason", StringType(),  True),
])

contracts_raw = [
    # (acct_no, product_code, status, start_date, end_date, amount, auto_renew, cancel_date, cancel_reason)
    ("SA-1001-WH",  "WH-GAS-STD",  "Active",    date(2018,3,15), None,             24.99, 1, None, None),
    ("SA-1005-WH",  "WH-GAS-PREM", "Active",    date(2016,8,22), None,             34.99, 1, None, None),
    ("SA-1010-WH",  "WH-GAS-STD",  "Active",    date(2015,4,12), None,             24.99, 1, None, None),
    ("SA-3001-MUR", "WH-ELEC-STD", "Active",    date(2016,6,1),  None,             19.99, 1, None, None),
    ("SA-3002-MUR", "WH-ELEC-STD", "Active",    date(2017,2,28), None,             19.99, 1, None, None),
    ("SA-3003-MUR", "WH-GAS-STD",  "Active",    date(2018,7,19), None,             24.99, 1, None, None),
    ("SA-3004-MUR", "WH-GAS-STD",  "Active",    date(2020,1,15), None,             24.99, 1, None, None),
    ("SA-3005-MUR", "WH-GAS-PREM", "Active",    date(2021,3,10), None,             34.99, 1, None, None),
    ("SA-2001-COM", "WH-GAS-PREM", "Active",    date(2015,11,1), None,             34.99, 1, None, None),
    ("SA-2003-COM", "WH-GAS-STD",  "Active",    date(2017,9,22), None,             24.99, 1, None, None),
    ("SA-2005-COM", "WH-GAS-STD",  "Active",    date(2019,10,7), None,             24.99, 1, None, None),
    ("SA-1001-GAS", "PP-HEAT",     "Active",    date(2018,4,1),  None,             39.99, 1, None, None),
    ("SA-1003-GAS", "PP-HEAT",     "Active",    date(2017,12,1), None,             39.99, 1, None, None),
    ("SA-1005-GAS", "PP-HEAT",     "Active",    date(2016,9,1),  None,             39.99, 1, None, None),
    ("SA-1007-GAS", "PP-HEAT",     "Active",    date(2019,10,1), None,             39.99, 1, None, None),
    ("SA-1009-GAS", "PP-HEAT",     "Active",    date(2018,3,1),  None,             39.99, 1, None, None),
    ("SA-1010-GAS", "PP-HEAT",     "Active",    date(2015,5,1),  None,             39.99, 1, None, None),
    ("SA-1012-GAS", "PP-HEAT",     "Active",    date(2017,9,1),  None,             39.99, 1, None, None),
    ("SA-1014-GAS", "PP-HEAT",     "Cancelled", date(2016,12,1), date(2022,11,30), 39.99, 0, date(2022,11,30), "Moved out of service area"),
    ("SA-1016-GAS", "PP-HEAT",     "Active",    date(2019,10,1), None,             39.99, 1, None, None),
    ("SA-1020-GAS", "PP-HEAT",     "Active",    date(2015,10,1), None,             39.99, 1, None, None),
    ("SA-1022-GAS", "PP-HEAT",     "Active",    date(2021,5,1),  None,             39.99, 1, None, None),
    ("SA-1024-GAS", "PP-HEAT",     "Active",    date(2020,1,1),  None,             39.99, 1, None, None),
    ("SA-1028-GAS", "PP-HEAT",     "Active",    date(2018,11,1), None,             39.99, 1, None, None),
    ("SA-1029-GAS", "PP-HEAT",     "Active",    date(2017,6,1),  None,             39.99, 1, None, None),
    ("SA-1003-COOL","PP-COOL",     "Active",    date(2019,5,1),  None,             24.99, 1, None, None),
    ("SA-1005-GAS", "PP-COOL",     "Active",    date(2016,5,1),  None,             24.99, 1, None, None),
    ("SA-1007-COOL","PP-COOL",     "Active",    date(2021,6,1),  None,             24.99, 1, None, None),
    ("SA-1012-COOL","PP-COOL",     "Active",    date(2020,5,1),  None,             24.99, 1, None, None),
    ("SA-1015-ELEC","PP-COOL",     "Active",    date(2023,2,1),  None,             24.99, 1, None, None),
    ("SA-1040-GAS", "PP-COOL",     "Active",    date(2022,7,1),  None,             24.99, 1, None, None),
    ("SA-1001-GAS", "PP-PLUMB",    "Active",    date(2019,1,1),  None,             14.99, 1, None, None),
    ("SA-1005-GAS", "PP-PLUMB",    "Active",    date(2017,1,1),  None,             14.99, 1, None, None),
    ("SA-1009-GAS", "PP-PLUMB",    "Active",    date(2020,1,1),  None,             14.99, 1, None, None),
    ("SA-1018-GAS", "PP-PLUMB",    "Cancelled", date(2019,1,1),  date(2023,6,30),  14.99, 0, date(2023,6,30), "Price sensitivity"),
    ("SA-1026-GAS", "PP-PLUMB",    "Active",    date(2016,8,1),  None,             14.99, 1, None, None),
    ("SA-1001-GAS", "PP-ELEC-HM",  "Active",    date(2022,1,1),  None,             19.99, 1, None, None),
    ("SA-1006-GAS", "PP-ELEC-HM",  "Active",    date(2022,1,1),  None,             19.99, 1, None, None),
    ("SA-1011-GAS", "PP-ELEC-HM",  "Active",    date(2022,6,1),  None,             19.99, 1, None, None),
    ("SA-1032-GAS", "PP-ELEC-HM",  "Active",    date(2022,3,1),  None,             19.99, 1, None, None),
    ("SA-1001-GAS", "SH-BASIC",    "Active",    date(2022,5,1),  None,             29.99, 1, None, None),
    ("SA-1003-GAS", "SH-BASIC",    "Active",    date(2021,10,1), None,             29.99, 1, None, None),
    ("SA-1007-GAS", "SH-BASIC",    "Active",    date(2021,1,1),  None,             29.99, 1, None, None),
    ("SA-1009-GAS", "SH-BASIC",    "Active",    date(2023,2,1),  None,             29.99, 1, None, None),
    ("SA-1012-GAS", "SH-BASIC",    "Active",    date(2020,1,1),  None,             29.99, 1, None, None),
    ("SA-1022-GAS", "SH-BASIC",    "Active",    date(2021,6,1),  None,             29.99, 1, None, None),
    ("SA-1025-GAS", "SH-BASIC",    "Active",    date(2021,1,1),  None,             29.99, 1, None, None),
    ("SA-1030-GAS", "SH-BASIC",    "Active",    date(2022,1,1),  None,             29.99, 1, None, None),
    ("SA-1005-GAS", "SH-PREM",     "Active",    date(2022,6,1),  None,             59.99, 1, None, None),
    ("SA-1010-GAS", "SH-PREM",     "Active",    date(2022,9,1),  None,             59.99, 1, None, None),
    ("SA-1015-ELEC","SH-PREM",     "Active",    date(2023,3,1),  None,             59.99, 1, None, None),
    ("SA-1033-GAS", "SH-PREM",     "Active",    date(2022,1,1),  None,             59.99, 1, None, None),
    ("SA-1040-GAS", "SH-PREM",     "Active",    date(2022,8,1),  None,             59.99, 1, None, None),
    ("SA-1001-GAS", "ECOBEE-INST", "Active",    date(2022,4,5),  date(2022,4,5),  249.00, 0, None, None),
    ("SA-1003-GAS", "ECOBEE-INST", "Active",    date(2021,9,12), date(2021,9,12), 249.00, 0, None, None),
    ("SA-1009-GAS", "ECOBEE-INST", "Active",    date(2023,1,28), date(2023,1,28), 249.00, 0, None, None),
]

contracts_data = [
    (i+1, sa_id_map[row[0]], product_code_map[row[1]], row[2], row[3], row[4], row[5], row[6], row[7], row[8])
    for i, row in enumerate(contracts_raw)
]

df_contracts = spark.createDataFrame(contracts_data, schema=contracts_schema)
df_contracts.write.format("delta").mode("overwrite").saveAsTable(f"{DEMO_LAKEHOUSE}.contracts")
print(f"  contracts: {df_contracts.count()} rows written")


# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

from pyspark.sql.types import *
from datetime import date

serial_id_map = {row[5]: row[0] for row in equip_raw}

sr_schema = StructType([
    StructField("request_id",         IntegerType(), False),
    StructField("service_account_id", IntegerType(), False),
    StructField("equipment_id",       IntegerType(), True),
    StructField("request_type",       StringType(),  False),
    StructField("priority",           StringType(),  False),
    StructField("status",             StringType(),  False),
    StructField("description",        StringType(),  True),
    StructField("created_date",       DateType(),    False),
    StructField("scheduled_date",     DateType(),    True),
    StructField("completed_date",     DateType(),    True),
    StructField("technician_id",      IntegerType(), True),
    StructField("resolution_notes",   StringType(),  True),
])

sr_raw = [
    # (acct_no, serial, type, priority, status, description, created, scheduled, completed, tech_id, notes)
    ("SA-1001-WH",  "RH2019-041847", "Maintenance",      "Low",       "Completed", "Annual flushing and anode rod check",        date(2022,11,15), date(2022,11,22), date(2022,11,22), 1012, "Anode rod 50% depleted, advised replacement within 2 years"),
    ("SA-1005-WH",  "BW2016-088231", "Emergency Repair", "Emergency", "Completed", "No hot water — pilot light out",             date(2023,2,8),   date(2023,2,8),   date(2023,2,8),   1007, "Thermocouple replaced, pilot relit, system tested OK"),
    ("SA-1010-GAS", "LX2015-105522", "Maintenance",      "Low",       "Completed", "Annual furnace tune-up",                    date(2022,9,20),  date(2022,10,5),  date(2022,10,5),  1023, "Filter replaced, heat exchanger inspected, combustion analysis done"),
    ("SA-1003-GAS", "CR2017-203811", "Emergency Repair", "High",      "Completed", "Furnace not starting — ignitor fault",       date(2023,1,12),  date(2023,1,13),  date(2023,1,13),  1007, "Hot surface ignitor cracked and replaced"),
    ("SA-1007-COOL","LX2021-AC9920", "Maintenance",      "Low",       "Completed", "Spring AC startup check",                   date(2023,5,2),   date(2023,5,8),   date(2023,5,8),   1019, "Refrigerant level OK, capacitor tested, coils cleaned"),
    ("SA-1012-COOL","GD2020-AC7741", "Emergency Repair", "High",      "Completed", "AC not cooling — refrigerant leak suspect",  date(2023,7,15),  date(2023,7,15),  date(2023,7,15),  1011, "Refrigerant leak found at service valve, repaired and recharged"),
    ("SA-1009-GAS", "LX2018-208410", "Maintenance",      "Low",       "Completed", "Annual furnace inspection",                 date(2022,10,10), date(2022,10,18), date(2022,10,18), 1023, "System clean, blower motor lubricated, all safeties tested"),
    ("SA-1016-GAS", "GD2019-394812", "Maintenance",      "Low",       "Completed", "Annual furnace tune-up",                    date(2023,9,25),  date(2023,10,3),  date(2023,10,3),  1015, "Completed standard inspection, new filter installed"),
    ("SA-1005-GAS", "YK2016-094520", "Maintenance",      "Low",       "Completed", "Annual furnace inspection",                 date(2023,9,28),  date(2023,10,10), date(2023,10,10), 1023, "All checks pass, heat exchanger clear"),
    ("SA-2001-COM", "RH2015-COM001", "Maintenance",      "Medium",    "Completed", "Quarterly commercial WH service",           date(2023,8,1),   date(2023,8,7),   date(2023,8,7),   1031, "Sediment flush completed, temperature verified at 60C"),
    ("SA-1001-GAS", "EB2022-TH3341", "Installation",     "Low",       "Completed", "ecobee thermostat install with app setup",  date(2022,4,4),   date(2022,4,5),   date(2022,4,5),   1019, "ecobee SmartThermostat Premium installed, integrated with furnace and AC"),
    ("SA-1003-GAS", "EB2021-TH1192", "Installation",     "Low",       "Completed", "ecobee enhanced thermostat install",        date(2021,9,10),  date(2021,9,12),  date(2021,9,12),  1019, "ecobee SmartThermostat Enhanced installed and WiFi configured"),
    ("SA-1015-ELEC","CR2023-HP0041", "Installation",     "Medium",    "Completed", "Heat pump install — replacing gas furnace", date(2023,1,30),  date(2023,2,10),  date(2023,2,10),  1008, "Carrier Infinity 20 installed, old furnace removed, system commissioned"),
    ("SA-1020-GAS", "LX2015-105522", "Emergency Repair", "High",      "Completed", "Furnace tripping limit switch repeatedly",  date(2023,12,21), date(2023,12,21), date(2023,12,21), 1007, "Dirty filter caused overheating, filter replaced, limit reset, all OK"),
    ("SA-1029-GAS", None,            "Maintenance",      "Low",       "Completed", "Annual maintenance check",                  date(2023,10,5),  date(2023,10,12), date(2023,10,12), 1015, "Inspection completed, minor adjustment to gas pressure"),
    ("SA-1018-GAS", None,            "Maintenance",      "Low",       "InProgress","Annual gas line inspection",                date(2024,4,20),  date(2024,4,28),  None,             1023, None),
    ("SA-1033-GAS", None,            "Maintenance",      "Low",       "InProgress","Annual furnace tune-up booking",            date(2024,4,18),  date(2024,4,30),  None,             1015, None),
    ("SA-3001-MUR", "RH2016-MUR001", "Maintenance",      "Medium",    "InProgress","Building WH annual service",               date(2024,4,22),  date(2024,4,25),  None,             1031, None),
    ("SA-1002-GAS", None,            "Maintenance",      "Low",       "Open",      "Customer-requested annual gas safety check",date(2024,4,28),  None,             None,             None, None),
    ("SA-1004-GAS", None,            "Maintenance",      "Low",       "Open",      "First annual furnace check (new build)",    date(2024,4,25),  None,             None,             None, None),
    ("SA-1006-GAS", None,            "Inspection",       "Medium",    "Open",      "Gas smell reported — investigate",          date(2024,4,30),  None,             None,             None, None),
    ("SA-1011-GAS", None,            "Emergency Repair", "High",      "Open",      "No heat — furnace off, house 14C",          date(2024,4,29),  None,             None,             None, None),
    ("SA-1013-GAS", None,            "Maintenance",      "Low",       "Open",      "Protection plan annual furnace service",    date(2024,4,27),  None,             None,             None, None),
    ("SA-1017-GAS", None,            "Inspection",       "Low",       "Open",      "Carbon monoxide detector triggered",        date(2024,4,26),  date(2024,5,2),   None,             None, None),
    ("SA-1019-GAS", None,            "Maintenance",      "Low",       "Open",      "Annual furnace check requested by steward", date(2024,4,23),  None,             None,             None, None),
    ("SA-1021-GAS", None,            "Emergency Repair", "Emergency", "Open",      "Water heater flooding — shut-off needed",   date(2024,4,30),  None,             None,             None, None),
    ("SA-1023-GAS", None,            "Maintenance",      "Low",       "Open",      "Pre-winter furnace inspection",             date(2024,4,24),  None,             None,             None, None),
    ("SA-1027-GAS", None,            "Installation",     "Medium",    "Open",      "New ecobee install — new construction",     date(2024,4,29),  date(2024,5,3),   None,             None, None),
    ("SA-2002-COM", None,            "Inspection",       "High",      "Open",      "Smoke detector triggered in HVAC room",     date(2024,4,30),  None,             None,             None, None),
    ("SA-3005-MUR", "BW2021-MUR001", "Emergency Repair", "High",      "Open",      "WH leaking — multi-unit building floor 3",  date(2024,4,30),  None,             None,             None, None),
]

sr_data = [
    (i+1, sa_id_map[row[0]], serial_id_map.get(row[1]) if row[1] else None,
     row[2], row[3], row[4], row[5], row[6], row[7], row[8], row[9], row[10])
    for i, row in enumerate(sr_raw)
]

df_sr = spark.createDataFrame(sr_data, schema=sr_schema)
df_sr.write.format("delta").mode("overwrite").saveAsTable(f"{DEMO_LAKEHOUSE}.service_requests")
print(f"  service_requests: {df_sr.count()} rows written")


# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

from pyspark.sql.types import *
from datetime import date, timedelta

billing_schema = StructType([
    StructField("transaction_id",    IntegerType(), False),
    StructField("contract_id",       IntegerType(), False),
    StructField("service_account_id",IntegerType(), False),
    StructField("transaction_type",  StringType(),  False),
    StructField("transaction_date",  DateType(),    False),
    StructField("due_date",          DateType(),    True),
    StructField("amount",            DoubleType(),  False),
    StructField("tax_amount",        DoubleType(),  False),
    StructField("payment_method",    StringType(),  True),
    StructField("status",            StringType(),  False),
    StructField("invoice_number",    StringType(),  True),
])

_onetime = {"ECOBEE-INST"}
_pay_methods = ["DirectDebit", "CreditCard", "Online"]
billing_data = []
txn_id = 1
monthly_charges = []

for i, row in enumerate(contracts_raw):
    cid = i + 1
    sa_id = sa_id_map[row[0]]
    product_code, status, start_date, monthly_amount = row[1], row[2], row[3], row[5]

    if product_code in _onetime:
        due = start_date + timedelta(days=30)
        billing_data.append((txn_id, cid, sa_id, "OneTimeCharge", start_date, due,
                              monthly_amount, round(monthly_amount * 0.13, 2),
                              "CreditCard", "Posted", f"INV-OT-{cid:05d}"))
        txn_id += 1
    elif status == "Active":
        pm = _pay_methods[cid % 3]
        for m in range(6):
            txn_date = date(2024, m + 1, 1)
            invoice = f"INV-2024{m+1:02d}-{cid:05d}"
            billing_data.append((txn_id, cid, sa_id, "MonthlyCharge",
                                  txn_date, txn_date + timedelta(days=15),
                                  monthly_amount, round(monthly_amount * 0.13, 2),
                                  pm, "Posted", invoice))
            monthly_charges.append((txn_id, cid, sa_id, txn_date, monthly_amount, pm, invoice))
            txn_id += 1

for _, cid, sa_id, txn_date, amount, pm, invoice in monthly_charges:
    if cid % 10 != 7:
        billing_data.append((txn_id, cid, sa_id, "Payment",
                              txn_date + timedelta(days=10), None,
                              -round(amount + round(amount * 0.13, 2), 2), 0.0,
                              pm, "Paid", invoice))
        txn_id += 1

df_billing = spark.createDataFrame(billing_data, schema=billing_schema)
df_billing.write.format("delta").mode("overwrite").saveAsTable(f"{DEMO_LAKEHOUSE}.billing_transactions")
print(f"  billing_transactions: {df_billing.count()} rows written")


# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

print("\n=== Row counts ===")
for tbl in ["customers", "service_accounts", "products", "equipment_registry",
            "contracts", "service_requests", "billing_transactions"]:
    n = spark.table(f"{DEMO_LAKEHOUSE}.{tbl}").count()
    print(f"  {tbl:<30} {n:>5} rows")

print("\nSetup complete.  Run nb_02_metadata_pipeline_demo.py next.")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# =============================================================================
# CALL CENTER EXTENSION — cc_agents (15 rows)
# =============================================================================
from pyspark.sql.types import *
from datetime import date

cc_agents_schema = StructType([
    StructField("agent_id",   IntegerType(), False),
    StructField("agent_name", StringType(),  False),
    StructField("team",       StringType(),  False),
    StructField("hire_date",  DateType(),    False),
])

cc_agents_data = [
    (1,  "Sarah Bouchard",    "billing",       date(2019, 3, 15)),
    (2,  "James Whitfield",   "billing",       date(2020, 7, 22)),
    (3,  "Priya Nair",        "billing",       date(2021, 1, 10)),
    (4,  "Michael Osei",      "billing",       date(2018, 11, 5)),
    (5,  "Tracey Henderson",  "pp_retentions", date(2019, 6, 14)),
    (6,  "Andre Lafleur",     "pp_retentions", date(2022, 2, 28)),
    (7,  "Kavita Rajan",      "pp_retentions", date(2020, 9, 17)),
    (8,  "David Kowalski",    "hvac_coord",    date(2021, 4, 12)),
    (9,  "Maria Santos",      "hvac_coord",    date(2019, 8, 3)),
    (10, "Thomas Bergeron",   "hvac_coord",    date(2022, 5, 20)),
    (11, "Lisa Nakamura",     "new_sales",     date(2020, 12, 1)),
    (12, "Raj Mehta",         "new_sales",     date(2021, 7, 8)),
    (13, "Patricia Sinclair", "new_sales",     date(2019, 10, 25)),
    (14, "Omar Farouk",       "emergency",     date(2022, 1, 15)),
    (15, "Nicole Tremblay",   "emergency",     date(2020, 3, 9)),
]

df_cc_agents = spark.createDataFrame(cc_agents_data, schema=cc_agents_schema)
df_cc_agents.write.format("delta").mode("overwrite").saveAsTable(f"{DEMO_LAKEHOUSE}.cc_agents")
print(f"  cc_agents: {df_cc_agents.count()} rows written")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# =============================================================================
# CALL CENTER EXTENSION — ref_cc_billing_adj_category (12 rows)
# =============================================================================
from pyspark.sql.types import *

# DEMO NOTE: This table mirrors dbo.ref_cc_billing_adjustment_category_new
# in Enercare's actual Azure SQL estate — currently ORPHANED there (no mappings,
# no descriptions). We recreate it here to demonstrate the governance gap.

ref_adj_schema = StructType([
    StructField("category_code", StringType(), False),
    StructField("category_desc", StringType(), False),
    StructField("adj_type",      StringType(), False),
])

ref_adj_data = [
    ("LATE_FEE_WAIVER",      "Late payment fee waived as courtesy",              "waiver"),
    ("DOUBLE_CHARGE_CREDIT", "Credit for duplicate billing charge",               "credit"),
    ("PLAN_PRICE_ADJ",       "Protection plan price adjustment",                  "credit"),
    ("SERVICE_CREDIT",       "Credit for incomplete or missed service visit",     "credit"),
    ("TAX_CORRECTION",       "Tax calculation correction applied",                "credit"),
    ("PAYMENT_REVERSAL",     "Reversed payment reapplied to account",             "charge"),
    ("GOODWILL_CREDIT",      "Goodwill gesture for customer experience issue",    "credit"),
    ("BILLING_ERROR_ADJ",    "Billing system error correction",                   "credit"),
    ("CONTRACT_DISPUTE_CR",  "Credit applied after contract dispute resolution",  "credit"),
    ("DIRECT_DEBIT_FAIL",    "Failed direct debit reprocessing fee",              "charge"),
    ("PROMO_ADJ",            "Promotional pricing adjustment",                    "credit"),
    ("OTHER",                "Miscellaneous billing adjustment",                  "waiver"),
]

df_ref_adj = spark.createDataFrame(ref_adj_data, schema=ref_adj_schema)
df_ref_adj.write.format("delta").mode("overwrite").saveAsTable(f"{DEMO_LAKEHOUSE}.ref_cc_billing_adj_category")
print(f"  ref_cc_billing_adj_category: {df_ref_adj.count()} rows written  [ORPHANED demo asset]")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# =============================================================================
# CALL CENTER EXTENSION — fct_cc_interactions (300 rows with demo correlation)
# Demo correlation: 14 customers who called billing in Jan-Feb 2026 are assigned
# a pp_renewal call within 30 days. 6/14 decline renewal → 57% acceptance rate
# (vs 76% for non-billing callers) — this is the 19pp gap Copilot surfaces.
# =============================================================================
import random
from datetime import date, timedelta
from pyspark.sql.types import *

random.seed(42)

Q_START    = date(2025, 10, 1)
Q_END      = date(2026, 3, 31)
DAYS_TOTAL = (Q_END - Q_START).days + 1  # 182

AGENT_BY_QUEUE = {
    "billing":       [1, 2, 3, 4],
    "pp_renewal":    [5, 6, 7, 8],
    "hvac_service":  [8, 9, 10],
    "emergency":     [14, 15],
    "new_pp_sales":  [11, 12, 13],
    "ecobee_support":[8, 9, 10],
    "general":       [1, 2, 3, 4],
}

FCR_RATES = {
    "billing": 0.61, "pp_renewal": 0.74, "hvac_service": 0.70,
    "emergency": 0.81, "new_pp_sales": 0.88, "ecobee_support": 0.79, "general": 0.83,
}
ESC_RATES = {
    "billing": 0.14, "pp_renewal": 0.08, "hvac_service": 0.11,
    "emergency": 0.19, "new_pp_sales": 0.04, "ecobee_support": 0.06, "general": 0.05,
}
HANDLE_TIMES = {
    "billing": (440, 95), "pp_renewal": (510, 120), "hvac_service": (380, 80),
    "emergency": (295, 65), "new_pp_sales": (550, 130), "ecobee_support": (360, 70), "general": (280, 60),
}
CSAT_PARAMS = {
    "fcr_resolved": (4.2, 0.6), "escalated": (2.1, 0.7),
    "pp_renewed": (4.0, 0.5), "pp_declined": (2.4, 0.8), "general_resolved": (3.8, 0.7),
}
BILLING_ADJ_POOL = [
    "LATE_FEE_WAIVER", "DOUBLE_CHARGE_CREDIT", "PLAN_PRICE_ADJ", "SERVICE_CREDIT",
    "GOODWILL_CREDIT", "BILLING_ERROR_ADJ", None, None, None, None,
]
DISPOSITIONS = {
    "billing":       ["billing_resolved", "billing_escalated", "credit_applied", "callback_scheduled"],
    "pp_renewal":    ["plan_renewed", "plan_cancelled", "callback_scheduled", "transfer_to_retentions"],
    "hvac_service":  ["appointment_scheduled", "sr_updated", "escalated_to_dispatch", "resolved_by_phone"],
    "emergency":     ["emergency_dispatch", "resolved_by_phone", "escalated"],
    "new_pp_sales":  ["plan_sold", "callback_scheduled", "no_interest"],
    "ecobee_support":["issue_resolved", "escalated", "warranty_claim"],
    "general":       ["resolved", "transferred", "callback_scheduled"],
}

# 14 correlation customers: billing call in Jan-Feb 2026 → pp_renewal within 30 days
# 6/14 decline renewal → 57% acceptance rate
CORR_CUSTOMERS = list(range(1, 15))   # customer_ids 1-14
CORR_DECLINES  = {1, 2, 3, 4, 5, 6}  # 6 of 14 decline


def _csat(q, pp_out, fcr, esc):
    if random.random() >= 0.22:
        return None
    if pp_out == "accepted":
        key = "pp_renewed"
    elif pp_out == "declined":
        key = "pp_declined"
    elif esc:
        key = "escalated"
    elif fcr:
        key = "fcr_resolved"
    else:
        key = "general_resolved"
    mu, sig = CSAT_PARAMS[key]
    return round(min(5.0, max(1.0, random.gauss(mu, sig))), 1)


def _make_row(iid, cust_id, q, idate, pp_out, is_corr_billing):
    agents = AGENT_BY_QUEUE[q]
    agent  = agents[iid % len(agents)]
    ht     = max(120, int(random.gauss(*HANDLE_TIMES[q])))
    hold   = random.randint(20, 180)
    fcr    = 1 if random.random() < FCR_RATES[q] else 0
    esc    = 1 if random.random() < ESC_RATES[q] else 0
    csat   = _csat(q, pp_out, fcr, esc)
    b_adj  = random.choice(BILLING_ADJ_POOL) if q == "billing" else None
    disp   = random.choice(DISPOSITIONS[q])
    chan   = random.choices(
        ["inbound_voice", "callback", "chat"], weights=[78, 14, 8])[0]
    date_key = int(idate.strftime("%Y%m%d"))
    return (iid, cust_id, agent, None, q, chan, idate, ht, hold, csat,
            fcr, esc, pp_out, b_adj, disp, date_key, is_corr_billing)


interactions_raw = []
iid = 1

# Correlation pairs: billing call then pp_renewal within 30 days
corr_billing_dates = {}
for idx, cust_id in enumerate(CORR_CUSTOMERS):
    bdate = date(2026, 1, 4) + timedelta(days=idx * 2)  # Jan 4 – Feb 1
    interactions_raw.append(_make_row(iid, cust_id, "billing", bdate, "not_applicable", True))
    corr_billing_dates[cust_id] = bdate
    iid += 1

for idx, cust_id in enumerate(CORR_CUSTOMERS):
    pdate  = corr_billing_dates[cust_id] + timedelta(days=15 + idx % 12)
    pp_out = "declined" if cust_id in CORR_DECLINES else "accepted"
    interactions_raw.append(_make_row(iid, cust_id, "pp_renewal", pdate, pp_out, False))
    iid += 1

# Remaining 272 interactions filling the queue distribution (300 - 28 corr = 272)
remaining_queues = (
    ["billing"]        * 79 +
    ["pp_renewal"]     * 58 +
    ["hvac_service"]   * 54 +
    ["emergency"]      * 27 +
    ["new_pp_sales"]   * 33 +
    ["ecobee_support"] * 12 +
    ["general"]        * 9
)  # 79+58+54+27+33+12+9 = 272
random.shuffle(remaining_queues)

for seq, q in enumerate(remaining_queues):
    cust_id = (seq % 50) + 1
    idate   = Q_START + timedelta(days=random.randint(0, DAYS_TOTAL - 1))
    if q == "pp_renewal":
        pp_out = random.choices(
            ["declined", "accepted", "callback"], weights=[22, 68, 10])[0]
    else:
        pp_out = "not_applicable"
    interactions_raw.append(_make_row(iid, cust_id, q, idate, pp_out, False))
    iid += 1

cc_int_schema = StructType([
    StructField("interaction_id",       IntegerType(), False),
    StructField("customer_id",          IntegerType(), False),
    StructField("agent_id",             IntegerType(), False),
    StructField("service_account_id",   IntegerType(), True),
    StructField("queue_type",           StringType(),  False),
    StructField("channel",              StringType(),  False),
    StructField("interaction_date",     DateType(),    False),
    StructField("handle_time_sec",      IntegerType(), False),
    StructField("hold_time_sec",        IntegerType(), False),
    StructField("csat_score",           DoubleType(),  True),
    StructField("fcr_flag",             IntegerType(), False),
    StructField("escalated_flag",       IntegerType(), False),
    StructField("pp_renewal_outcome",   StringType(),  True),
    StructField("billing_adj_category", StringType(),  True),
    StructField("disposition_code",     StringType(),  False),
    StructField("interaction_date_key", IntegerType(), False),
])

int_data = [row[:16] for row in interactions_raw]  # drop is_corr_billing flag
df_cc_int = spark.createDataFrame(int_data, schema=cc_int_schema)
df_cc_int.write.format("delta").mode("overwrite").saveAsTable(f"{DEMO_LAKEHOUSE}.fct_cc_interactions")
print(f"  fct_cc_interactions: {df_cc_int.count()} rows written")

# Validate demo correlation
_corr_csv = ",".join(str(c) for c in CORR_CUSTOMERS)
_check = spark.sql(f"""
    SELECT SUM(CASE WHEN pp_renewal_outcome = 'accepted' THEN 1 ELSE 0 END) * 1.0
           / NULLIF(COUNT(*), 0) AS renewal_rate
    FROM {DEMO_LAKEHOUSE}.fct_cc_interactions
    WHERE queue_type = 'pp_renewal'
      AND interaction_date BETWEEN '2026-01-01' AND '2026-03-31'
      AND customer_id IN ({_corr_csv})
""").first()
_rate = float(_check.renewal_rate) if _check.renewal_rate else 0.0
print(f"Demo correlation check: PP renewal rate (billing callers Q1): {_rate:.1%}  [target: ~57%]")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# =============================================================================
# CALL CENTER EXTENSION — fct_cc_transcript_turns (~12 turns/interaction)
# Billing calls for correlation customers include billing-confusion phrases
# so the Data Agent can surface the root cause of PP renewal decline.
# =============================================================================
BILLING_CUST = [
    "I don't understand why my bill went up this month",
    "I'm seeing two charges and I only have one plan",
    "My protection plan price changed and nobody told me",
    "Can you credit my account for the service that wasn't completed",
    "I want to dispute this charge on my invoice",
    "The invoice date doesn't match when I signed up",
    "I've been overcharged for three months in a row",
    "Why did Zuora send me two invoices?",
    "I thought I was on the monthly plan but this looks annual",
]
BILLING_CONFUSION = [
    "I have some billing confusion about the charges on my account",
    "I'm looking at this invoice and I'm being charged twice it seems",
    "There's a billing confusion here — can you explain why I was charged twice?",
    "This invoice does not match what I agreed to pay",
    "I'm confused about this invoice — the amounts just don't add up",
]
BILLING_AGENT = [
    "I can see your account has a billing cycle change from last month",
    "Let me apply a one-time credit to your account",
    "I'll escalate this to our billing specialist team",
    "I can confirm the charge is correct because your plan renewed on that date",
    "I'm waiving the late fee as a one-time courtesy",
]
PP_RENEWAL_CUST = [
    "I got a renewal notice but I'm thinking about cancelling",
    "What does my protection plan actually cover this year",
    "Is there a discount if I renew for two years",
    "I'm moving next month, can I transfer the plan to the new address",
    "I've had three repairs this year and I'm not sure it's worth it",
    "The price went up fifteen percent, why?",
    "My neighbor has the same plan and pays less",
]
HVAC_CUST = [
    "My furnace stopped working and I need someone today",
    "I've been waiting three weeks for my annual maintenance",
    "The technician came but the problem still isn't fixed",
    "I need to reschedule my maintenance appointment",
    "What's the status of my service request number",
    "It's minus twenty outside and my heat isn't working",
]
EMERGENCY_CUST = [
    "My hot water heater is leaking right now",
    "No heat in the middle of winter, this is an emergency",
    "Water is coming out of the furnace",
    "Carbon monoxide alarm is going off near my furnace",
    "I smell gas near my water heater",
]
GENERIC_CUST = [
    "I'd like to get more information about a protection plan",
    "My ecobee thermostat isn't connecting to the app",
    "I have a general question about my account",
    "I'd like to schedule a service for my equipment",
    "Can you check the status of my account?",
]
GENERIC_AGENT = [
    "Thank you for calling Enercare, how can I help you today?",
    "I'd be happy to look into that for you",
    "Let me pull up your account details",
    "I can see your account and I'm reviewing your history now",
    "Is there anything else I can help you with today?",
    "I've updated your account with the changes we discussed",
    "You'll receive an email confirmation within 24 hours",
]
CUST_PHRASES = {
    "billing": BILLING_CUST, "pp_renewal": PP_RENEWAL_CUST,
    "hvac_service": HVAC_CUST, "emergency": EMERGENCY_CUST,
    "new_pp_sales": GENERIC_CUST, "ecobee_support": GENERIC_CUST, "general": GENERIC_CUST,
}
AGENT_PHRASES = {
    "billing": BILLING_AGENT,
}
INTENT_DIST = {
    "billing":      ["billing_dispute", "payment_question", "invoice_inquiry", "general"],
    "pp_renewal":   ["pp_cancel_intent", "renewal_inquiry", "price_negotiation", "transfer_request"],
    "hvac_service": ["hvac_complaint", "scheduling_request", "status_inquiry", "general"],
    "emergency":    ["hvac_complaint", "emergency_dispatch", "general"],
}

corr_billing_iids = {row[0] for row in interactions_raw if row[16]}

transcript_rows = []
turn_id = 1

for int_row in interactions_raw:
    int_id  = int_row[0]
    queue   = int_row[4]
    fcr     = int_row[10]
    esc     = int_row[11]
    is_corr = int_row[16]

    n_turns       = random.randint(6, 18)
    added_conf    = False
    cust_pool     = CUST_PHRASES.get(queue, GENERIC_CUST)
    agent_pool    = AGENT_PHRASES.get(queue, GENERIC_AGENT)

    for t in range(1, n_turns + 1):
        speaker = "customer" if t % 2 == 1 else "agent"

        if speaker == "customer":
            if is_corr and not added_conf and t >= 3:
                text = random.choice(BILLING_CONFUSION)
                added_conf = True
            else:
                text = random.choice(cust_pool)
        else:
            text = random.choice(agent_pool)

        progress = t / n_turns
        if esc:
            sent = random.gauss(-0.15 - progress * 0.5, 0.2)
        elif fcr:
            sent = random.gauss(progress * 0.45, 0.2)
        else:
            sent = random.gauss(-0.05, 0.2)
        sent = round(max(-1.0, min(1.0, sent)), 3)

        intent = None
        if speaker == "customer" and queue in INTENT_DIST:
            intent = random.choice(INTENT_DIST[queue])

        transcript_rows.append((turn_id, int_id, t, speaker, text, sent, intent))
        turn_id += 1

    if is_corr and not added_conf:
        transcript_rows.append((
            turn_id, int_id, n_turns + 1, "customer",
            random.choice(BILLING_CONFUSION), -0.3, "billing_dispute",
        ))
        turn_id += 1

turn_schema = StructType([
    StructField("turn_id",        IntegerType(), False),
    StructField("interaction_id", IntegerType(), False),
    StructField("turn_seq",       IntegerType(), False),
    StructField("speaker",        StringType(),  False),
    StructField("utterance_text", StringType(),  False),
    StructField("sentiment_score",DoubleType(),  False),
    StructField("intent_label",   StringType(),  True),
])

df_turns = spark.createDataFrame(transcript_rows, schema=turn_schema)
df_turns.write.format("delta").mode("overwrite").saveAsTable(f"{DEMO_LAKEHOUSE}.fct_cc_transcript_turns")
print(f"  fct_cc_transcript_turns: {df_turns.count()} rows written")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# =============================================================================
# CALL CENTER EXTENSION — Summary
# =============================================================================
print("\nCall center tables written:")
for tbl, note in [
    ("cc_agents",                    ""),
    ("ref_cc_billing_adj_category",  "  [ORPHANED demo asset]"),
    ("fct_cc_interactions",          ""),
    ("fct_cc_transcript_turns",      ""),
]:
    n = spark.table(f"{DEMO_LAKEHOUSE}.{tbl}").count()
    print(f"  {tbl:<35} {n:>6} rows{note}")

print("\nAll tables ready. Run nb_02_metadata_pipeline_demo.py next.")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

