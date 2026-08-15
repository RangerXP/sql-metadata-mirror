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
# META       "default_lakehouse_workspace_id": "b976cac2-7754-4061-88c2-61c0ac016a99",
# META       "known_lakehouses": [
# META         {
# META           "id": "e9b09e4e-b7b9-4208-b9ec-bb3433154555"
# META         }
# META       ]
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
# in Enercare's actual Azure SQL estate. "Orphaned" here means it currently
# has no semantic-model mapping or curated metadata; it is not a pipeline blocker.

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
print(
    f"  ref_cc_billing_adj_category: {df_ref_adj.count()} rows written"
    "  [ORPHANED demo asset - informational only, not blocking nb_04]"
)

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
    ("ref_cc_billing_adj_category",  "  [ORPHANED demo asset - optional governance review]"),
    ("fct_cc_interactions",          ""),
    ("fct_cc_transcript_turns",      ""),
]:
    n = spark.table(f"{DEMO_LAKEHOUSE}.{tbl}").count()
    print(f"  {tbl:<35} {n:>6} rows{note}")

print("\nAll tables ready. Run nb_02_metadata_pipeline_demo.py next.")
print("Orphaned note is informational only and does not block nb_04_sempy_writeback.")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************


# CELL ********************

# Fabric Notebook: nb_05a_publish_synthetic_data_to_sql
# Purpose: Publish the seven transactional Enercare source tables from
#          lh_enercare_demo into Azure SQL in sub2 so SQL becomes the
#          authoritative mirrored source.
#
# Run after:
#   - nb_01_setup_demo_environment
#   - sql/02_sub2_sql_source_schema.sql executed against sqldemo
#
# DEMO_MODE = True  -> dry-run only
# DEMO_MODE = False -> acquire an Entra token and write rows to Azure SQL

from pyspark.sql import functions as F

DEMO_MODE                 = False
NOTEBOOK_BUILD_TAG        = "2026-06-17 notebook-owned-sql-truncation-fix"
DEMO_LAKEHOUSE            = "lh_enercare_demo"
WORKSPACE_ID              = "795ce5db-7ea0-4a7c-ba64-e27c9fb568f4"
SERVER_NAME               = "sqlserver-sk2wus3.database.windows.net"
DATABASE_NAME             = "sqldemo"
SQL_PORT                  = 1433
SQL_LOGIN_TIMEOUT_SECONDS = 30
TARGET_SCHEMA             = "dbo"
BASE_TABLE_LOAD_MODE      = "skip_existing"  # replace | append | skip_existing  (replace requires tokenlibrary mode)
PHASE_B_CHILD_TABLES      = ["customer_complaints", "customer_consents"]
SQL_AUTH_MODE             = "auto"  # auto | managed_identity | tokenlibrary
SQL_MANAGED_IDENTITY_CLIENT_ID = ""  # Optional: set for user-assigned MI
EFFECTIVE_SQL_AUTH_MODE   = SQL_AUTH_MODE
TABLE_PRIMARY_KEYS        = {
    "products": ["product_id"],
    "customers": ["customer_id"],
    "service_accounts": ["service_account_id"],
    "equipment_registry": ["equipment_id"],
    "contracts": ["contract_id"],
    "service_requests": ["request_id"],
    "billing_transactions": ["transaction_id"],
}
LOAD_ORDER = [
    "products",
    "customers",
    "service_accounts",
    "equipment_registry",
    "contracts",
    "service_requests",
    "billing_transactions",
]

print(f"nb_05a_publish_synthetic_data_to_sql | DEMO_MODE={DEMO_MODE}")
print(f"Notebook build : {NOTEBOOK_BUILD_TAG}")
print(f"Workspace      : {WORKSPACE_ID}")
print(f"Source lakehouse: {DEMO_LAKEHOUSE}")
print(f"Target SQL DB  : {SERVER_NAME}:{SQL_PORT} / {DATABASE_NAME}")
print(f"Target schema  : {TARGET_SCHEMA}")
print(f"Base load mode : {BASE_TABLE_LOAD_MODE}")
print(f"SQL auth mode  : {SQL_AUTH_MODE}")
print("Load order     :", ", ".join(LOAD_ORDER))


# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# Cell 2: JDBC/ODBC config and authentication helpers

import struct
import time
import pyodbc

ODBC_SQL_COPT_SS_ACCESS_TOKEN = 1256
sql_access_token = None
conn = None

JDBC_URL = (
    f"jdbc:sqlserver://{SERVER_NAME}:{SQL_PORT};"
    f"database={DATABASE_NAME};"
    "encrypt=true;"
    "trustServerCertificate=false;"
    "hostNameInCertificate=*.database.windows.net;"
    f"loginTimeout={SQL_LOGIN_TIMEOUT_SECONDS};"
)


def get_sql_access_token():
    scopes = [
        "https://database.windows.net/",
        "https://database.windows.net",
    ]
    last_error = None
    for scope in scopes:
        started_at = time.time()
        print(f"Requesting Azure SQL token for scope: {scope}")
        try:
            token = mssparkutils.credentials.getToken(scope)
            elapsed_seconds = round(time.time() - started_at, 1)
            print(f"Acquired Azure SQL token for scope: {scope} in {elapsed_seconds} seconds")
            return token
        except Exception as exc:
            elapsed_seconds = round(time.time() - started_at, 1)
            print(f"Token acquisition failed for scope: {scope} after {elapsed_seconds} seconds")
            print(str(exc))
            last_error = exc
    if last_error is not None:
        raise last_error
    raise RuntimeError("Azure SQL token acquisition failed before any token request was attempted.")


def transform_for_sql(table_name, df):
    if table_name == "products":
        return df.withColumn("is_active", F.col("is_active").cast("boolean"))
    if table_name == "contracts":
        return df.withColumn("auto_renew", F.col("auto_renew").cast("boolean"))
    return df


def is_managed_identity_jdbc_available() -> bool:
    try:
        spark._jvm.java.lang.Class.forName("com.azure.identity.ManagedIdentityCredentialBuilder")
        return True
    except Exception:
        return False



def apply_jdbc_auth(reader, access_token=None):
    if EFFECTIVE_SQL_AUTH_MODE == "managed_identity":
        reader = reader.option("authentication", "ActiveDirectoryMSI")
        if SQL_MANAGED_IDENTITY_CLIENT_ID:
            reader = reader.option("msiClientId", SQL_MANAGED_IDENTITY_CLIENT_ID)
        return reader

    if EFFECTIVE_SQL_AUTH_MODE == "tokenlibrary":
        if not access_token:
            raise RuntimeError("Tokenlibrary auth selected but no access token was provided.")
        return reader.option("accessToken", access_token)

    raise ValueError("EFFECTIVE_SQL_AUTH_MODE must be one of: managed_identity, tokenlibrary")


def read_target_count(table_name, access_token):
    target_table = f"{TARGET_SCHEMA}.{table_name}"
    query = f"SELECT COUNT(1) AS row_count FROM {target_table}"
    reader = (
        spark.read.format("jdbc")
        .option("url", JDBC_URL)
        .option("driver", "com.microsoft.sqlserver.jdbc.SQLServerDriver")
        .option("query", query)
    )
    count_df = apply_jdbc_auth(reader, access_token).load()
    return int(count_df.first()["row_count"])


def read_target_keys(table_name, key_columns, access_token):
    target_table = f"{TARGET_SCHEMA}.{table_name}"
    key_list = ", ".join(key_columns)
    query = f"SELECT {key_list} FROM {target_table}"
    reader = (
        spark.read.format("jdbc")
        .option("url", JDBC_URL)
        .option("driver", "com.microsoft.sqlserver.jdbc.SQLServerDriver")
        .option("query", query)
    )
    return apply_jdbc_auth(reader, access_token).load().select(*key_columns).dropDuplicates()


def get_sql_odbc_connection(access_token):
    conn_str = (
        "Driver={ODBC Driver 18 for SQL Server};"
        f"Server=tcp:{SERVER_NAME},{SQL_PORT};"
        f"Database={DATABASE_NAME};"
        "Encrypt=yes;"
        "TrustServerCertificate=no;"
        f"Connection Timeout={SQL_LOGIN_TIMEOUT_SECONDS};"
    )

    if EFFECTIVE_SQL_AUTH_MODE == "managed_identity":
        conn_str += "Authentication=ActiveDirectoryMsi;"
        if SQL_MANAGED_IDENTITY_CLIENT_ID:
            conn_str += f"UID={SQL_MANAGED_IDENTITY_CLIENT_ID};"
        return pyodbc.connect(conn_str, autocommit=False)

    if EFFECTIVE_SQL_AUTH_MODE == "tokenlibrary":
        odbc_token = access_token.encode("utf-16-le")
        token_struct = struct.pack(f"<I{len(odbc_token)}s", len(odbc_token), odbc_token)
        return pyodbc.connect(
            conn_str,
            attrs_before={ODBC_SQL_COPT_SS_ACCESS_TOKEN: token_struct},
            autocommit=False,
        )

    raise ValueError("EFFECTIVE_SQL_AUTH_MODE must be one of: managed_identity, tokenlibrary")


if DEMO_MODE:
    print("[DRY RUN] Skipping SQL authentication setup.")
else:
    EFFECTIVE_SQL_AUTH_MODE = SQL_AUTH_MODE

    if SQL_AUTH_MODE == "auto":
        if is_managed_identity_jdbc_available():
            EFFECTIVE_SQL_AUTH_MODE = "managed_identity"
            print("Using managed identity authentication for Azure SQL JDBC (auto mode).")
        else:
            EFFECTIVE_SQL_AUTH_MODE = "tokenlibrary"
            print("[WARN] Managed identity JDBC classpath is unavailable in this runtime.")
            print("[INFO] Falling back to TokenLibrary authentication for JDBC.")
            sql_access_token = get_sql_access_token()
            print("Acquired Microsoft Entra access token for Azure SQL.")
    elif SQL_AUTH_MODE == "tokenlibrary":
        EFFECTIVE_SQL_AUTH_MODE = "tokenlibrary"
        sql_access_token = get_sql_access_token()
        print("Acquired Microsoft Entra access token for Azure SQL.")
    elif SQL_AUTH_MODE == "managed_identity":
        if not is_managed_identity_jdbc_available():
            EFFECTIVE_SQL_AUTH_MODE = "tokenlibrary"
            print("[WARN] Managed identity JDBC classpath is unavailable in this runtime.")
            print("[INFO] Falling back to TokenLibrary authentication for JDBC.")
            sql_access_token = get_sql_access_token()
            print("Acquired Microsoft Entra access token for Azure SQL.")
        else:
            EFFECTIVE_SQL_AUTH_MODE = "managed_identity"
            print("Using managed identity authentication for Azure SQL JDBC (MI mode).")
    else:
        raise ValueError("SQL_AUTH_MODE must be one of: auto, managed_identity, tokenlibrary")

    print(f"Effective SQL auth mode: {EFFECTIVE_SQL_AUTH_MODE}")
    print("[INFO] pyodbc connection deferred — it will be created only if Phase B/replace control-plane statements need it.")


# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# Cell 3: Source inventory and preflight validation

source_inventory = []
for table_name in LOAD_ORDER:
    source_df = spark.table(f"{DEMO_LAKEHOUSE}.{table_name}")
    source_count = source_df.count()
    source_inventory.append((table_name, source_count))
    print(f"Source table {table_name:<20} {source_count:>5} rows")

inventory_df = spark.createDataFrame(source_inventory, ["table_name", "source_row_count"])
display(inventory_df)

if DEMO_MODE:
    print("[DRY RUN] Execute sql/02_sub2_sql_source_schema.sql before running with DEMO_MODE=False.")
    print("[DRY RUN] This notebook appends rows into the target SQL tables in dependency order.")


# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# Cell 4: Publish source tables to Azure SQL


def clear_base_tables(connection):
    cur = connection.cursor()
    print("Clearing base tables in reverse dependency order before reload...")
    for table_name in PHASE_B_CHILD_TABLES:
        target_table = f"{TARGET_SCHEMA}.{table_name}"
        cur.execute("SELECT OBJECT_ID(?)", target_table)
        if cur.fetchone()[0] is not None:
            print(f"  DELETE FROM {target_table}")
            cur.execute(f"DELETE FROM {target_table}")

    for table_name in reversed(LOAD_ORDER):
        target_table = f"{TARGET_SCHEMA}.{table_name}"
        print(f"  DELETE FROM {target_table}")
        cur.execute(f"DELETE FROM {target_table}")
    connection.commit()


def ensure_service_request_employee_fk_ready(connection):
    cur = connection.cursor()

    cur.execute("SELECT OBJECT_ID(N'dbo.service_requests', N'U')")
    has_service_requests = cur.fetchone()[0] is not None
    cur.execute("SELECT OBJECT_ID(N'dbo.employees', N'U')")
    has_employees = cur.fetchone()[0] is not None

    if not has_service_requests or not has_employees:
        return

    cur.execute(
        """
        SELECT 1
        FROM sys.foreign_keys
        WHERE name = 'FK_service_requests_employee'
          AND parent_object_id = OBJECT_ID(N'dbo.service_requests')
        """
    )
    if cur.fetchone() is None:
        return

    technician_rows = (
        spark.table(f"{DEMO_LAKEHOUSE}.service_requests")
        .select("technician_id")
        .where(F.col("technician_id").isNotNull())
        .dropDuplicates()
        .collect()
    )
    technician_ids = sorted({int(row["technician_id"]) for row in technician_rows})
    if not technician_ids:
        return

    placeholders = ", ".join(["?"] * len(technician_ids))
    cur.execute(
        f"SELECT employee_id FROM dbo.employees WHERE employee_id IN ({placeholders})",
        technician_ids,
    )
    existing_ids = {int(row[0]) for row in cur.fetchall()}
    missing_ids = [employee_id for employee_id in technician_ids if employee_id not in existing_ids]

    if not missing_ids:
        print("FK preflight: all technician IDs already exist in dbo.employees.")
        return

    print(f"FK preflight: inserting {len(missing_ids)} placeholder dbo.employees rows for technician IDs.")
    employee_rows = [
        (
            employee_id,
            f"tech{employee_id}@enercare.ca",
            f"Tech{employee_id}",
            "Placeholder",
            f"tech{employee_id}@enercare.ca",
            None,
            "Service Technician",
            "Field Ops",
            None,
            "2020-01-01",
            None,
            None,
            None,
            1,
        )
        for employee_id in missing_ids
    ]

    cur.fast_executemany = True
    cur.executemany(
        """
        INSERT INTO dbo.employees (
            employee_id, upn, first_name, last_name, email, phone, role,
            department, manager_employee_id, hire_date, sin_full,
            date_of_birth, home_postal_code, is_active
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        employee_rows,
    )
    connection.commit()
    print("FK preflight: placeholder employee rows committed.")

if DEMO_MODE:
    print("[DRY RUN] No JDBC writes attempted.")
else:
    if BASE_TABLE_LOAD_MODE not in {"append", "replace", "skip_existing"}:
        raise ValueError("BASE_TABLE_LOAD_MODE must be one of: append, replace, skip_existing")

    if BASE_TABLE_LOAD_MODE == "replace":
        if conn is None and EFFECTIVE_SQL_AUTH_MODE == "tokenlibrary":
            conn = get_sql_odbc_connection(sql_access_token)
            print("pyodbc connection established for replace-mode DELETE operations.")
        if conn is None:
            raise RuntimeError(
                "BASE_TABLE_LOAD_MODE='replace' requires pyodbc DELETE operations. "
                "Set SQL_AUTH_MODE='tokenlibrary' or change BASE_TABLE_LOAD_MODE to 'append' or 'skip_existing'."
            )
        clear_base_tables(conn)

    if conn is None:
        conn = get_sql_odbc_connection(sql_access_token)
        print("pyodbc connection established for FK preflight checks.")

    ensure_service_request_employee_fk_ready(conn)

    write_results = []

    for table_name in LOAD_ORDER:
        target_table = f"{TARGET_SCHEMA}.{table_name}"
        source_df = transform_for_sql(table_name, spark.table(f"{DEMO_LAKEHOUSE}.{table_name}"))
        source_count = source_df.count()
        write_df = source_df
        write_count = source_count

        print(f"Writing {table_name} -> {target_table} ({source_count} rows)")

        if BASE_TABLE_LOAD_MODE == "skip_existing":
            key_columns = TABLE_PRIMARY_KEYS.get(table_name, [])
            if key_columns and all(col in source_df.columns for col in key_columns):
                existing_keys_df = read_target_keys(table_name, key_columns, sql_access_token)
                write_df = source_df.alias("src").join(existing_keys_df.alias("tgt"), on=key_columns, how="left_anti")
                write_count = write_df.count()
                skipped_count = source_count - write_count
                if skipped_count > 0:
                    print(f"Skipped {skipped_count} existing rows in {target_table} based on keys {key_columns}.")
            else:
                print(f"[WARN] No valid primary key mapping found for {table_name}; writing all source rows.")

            if write_count == 0:
                target_count = read_target_count(table_name, sql_access_token)
                write_results.append((table_name, source_count, target_count, True))
                print(f"Skipped {target_table}: no new rows to insert.")
                continue

        (
            apply_jdbc_auth(
                write_df.write.format("jdbc")
            .option("url", JDBC_URL)
            .option("driver", "com.microsoft.sqlserver.jdbc.SQLServerDriver")
            .option("dbtable", target_table)
            ,
                sql_access_token,
            )
            .mode("append")
            .save()
        )

        target_count = read_target_count(table_name, sql_access_token)
        write_results.append((table_name, source_count, target_count, target_count >= source_count))
        print(f"Validated {target_table}: {target_count} rows now present")

    results_df = spark.createDataFrame(
        write_results,
        ["table_name", "source_row_count", "target_row_count", "target_at_least_source"],
    )
    print("Publish complete.")
    display(results_df)


# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# Cell 5: Post-run notes

print("Next steps:")
print("  1. Reconcile exact row counts in Azure SQL after the initial load.")
print("  2. Create SQL views/procs for metadata extraction only after the source tables are stable.")
print("  3. Stand up Fabric mirroring against the Azure SQL source.")
print("  4. If rerunning this load, clear target tables in reverse dependency order first.")


# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# Cell B0: Confirm pyodbc connection for Phase B SQL script execution

if DEMO_MODE:
    print("[DRY RUN] Skipping pyodbc connection setup for Phase B cells.")
elif EFFECTIVE_SQL_AUTH_MODE == "managed_identity":
    print("[WARN] Phase B DDL/seed cells require pyodbc and are not available in managed_identity mode.")
    print("[WARN] Switch SQL_AUTH_MODE='tokenlibrary' to run Phase B cells.")
else:
    try:
        conn.cursor().execute("SELECT 1")
        print("pyodbc connection ready for Phase B cells.")
    except Exception:
        conn = get_sql_odbc_connection(sql_access_token)
        print("pyodbc connection re-established for Phase B cells.")


# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# CELL B0A: Define notebook-owned SQL scripts

PURVIEW_DEMO_EXTENSIONS_SQL = r"""
SET NOCOUNT ON;
GO
IF COL_LENGTH('dbo.customers', 'date_of_birth') IS NULL ALTER TABLE dbo.customers ADD date_of_birth DATE NULL;
GO
IF COL_LENGTH('dbo.customers', 'sin_last_4') IS NULL ALTER TABLE dbo.customers ADD sin_last_4 CHAR(4) NULL;
GO
IF COL_LENGTH('dbo.customers', 'owner_email') IS NULL ALTER TABLE dbo.customers ADD owner_email VARCHAR(255) NULL;
GO
IF COL_LENGTH('dbo.customers', 'marketing_consent') IS NULL ALTER TABLE dbo.customers ADD marketing_consent BIT NULL;
GO
IF COL_LENGTH('dbo.service_accounts', 'latitude') IS NULL ALTER TABLE dbo.service_accounts ADD latitude DECIMAL(9, 6) NULL;
GO
IF COL_LENGTH('dbo.service_accounts', 'longitude') IS NULL ALTER TABLE dbo.service_accounts ADD longitude DECIMAL(9, 6) NULL;
GO
IF COL_LENGTH('dbo.service_accounts', 'service_zone_code') IS NULL ALTER TABLE dbo.service_accounts ADD service_zone_code VARCHAR(16) NULL;
GO
IF COL_LENGTH('dbo.service_requests', 'no_show_reason_code') IS NULL ALTER TABLE dbo.service_requests ADD no_show_reason_code VARCHAR(64) NULL;
GO
IF COL_LENGTH('dbo.billing_transactions', 'bank_routing_last_4') IS NULL ALTER TABLE dbo.billing_transactions ADD bank_routing_last_4 CHAR(4) NULL;
GO
IF COL_LENGTH('dbo.billing_transactions', 'card_pan_last_4') IS NULL ALTER TABLE dbo.billing_transactions ADD card_pan_last_4 CHAR(4) NULL;
GO
IF OBJECT_ID(N'dbo.employees', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.employees (
        employee_id INT NOT NULL,
        upn VARCHAR(255) NOT NULL,
        first_name NVARCHAR(100) NOT NULL,
        last_name NVARCHAR(100) NOT NULL,
        email VARCHAR(255) NOT NULL,
        phone VARCHAR(25) NULL,
        role VARCHAR(64) NOT NULL,
        department VARCHAR(64) NOT NULL,
        manager_employee_id INT NULL,
        hire_date DATE NOT NULL,
        sin_full CHAR(11) NULL,
        date_of_birth DATE NULL,
        home_postal_code VARCHAR(10) NULL,
        is_active BIT NOT NULL,
        CONSTRAINT PK_employees PRIMARY KEY CLUSTERED (employee_id),
        CONSTRAINT UQ_employees_upn UNIQUE (upn)
    );
END
GO
IF OBJECT_ID(N'dbo.service_zones', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.service_zones (
        zone_code VARCHAR(16) NOT NULL,
        zone_name NVARCHAR(100) NOT NULL,
        parent_zone_code VARCHAR(16) NULL,
        province CHAR(2) NOT NULL,
        zone_manager_upn VARCHAR(255) NULL,
        sla_target_minutes INT NULL,
        CONSTRAINT PK_service_zones PRIMARY KEY CLUSTERED (zone_code)
    );
END
GO
IF OBJECT_ID(N'dbo.customer_consents', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.customer_consents (
        consent_id INT NOT NULL,
        customer_id INT NOT NULL,
        consent_type VARCHAR(40) NOT NULL,
        consent_status VARCHAR(16) NOT NULL,
        legal_basis VARCHAR(40) NOT NULL,
        granted_date DATE NULL,
        withdrawn_date DATE NULL,
        source_channel VARCHAR(40) NULL,
        captured_by_upn VARCHAR(255) NULL,
        CONSTRAINT PK_customer_consents PRIMARY KEY CLUSTERED (consent_id),
        CONSTRAINT FK_customer_consents_customer FOREIGN KEY (customer_id) REFERENCES dbo.customers (customer_id)
    );
END
GO
IF OBJECT_ID(N'dbo.customer_complaints', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.customer_complaints (
        complaint_id INT NOT NULL,
        customer_id INT NOT NULL,
        service_account_id INT NULL,
        complaint_type VARCHAR(40) NOT NULL,
        severity VARCHAR(32) NOT NULL,
        opened_date DATE NOT NULL,
        closed_date DATE NULL,
        status VARCHAR(24) NOT NULL,
        assigned_to_upn VARCHAR(255) NULL,
        description NVARCHAR(1000) NULL,
        regulator_case_ref VARCHAR(64) NULL,
        CONSTRAINT PK_customer_complaints PRIMARY KEY CLUSTERED (complaint_id),
        CONSTRAINT FK_customer_complaints_customer FOREIGN KEY (customer_id) REFERENCES dbo.customers (customer_id),
        CONSTRAINT FK_customer_complaints_service_account FOREIGN KEY (service_account_id) REFERENCES dbo.service_accounts (service_account_id)
    );
END
GO
IF OBJECT_ID(N'dbo.customer_complaints', N'U') IS NOT NULL
   AND COL_LENGTH('dbo.customer_complaints', 'severity') IS NOT NULL
BEGIN
    ALTER TABLE dbo.customer_complaints ALTER COLUMN severity VARCHAR(32) NOT NULL;
END
GO
IF OBJECT_ID(N'dbo.data_owners_directory', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.data_owners_directory (
        owner_id INT NOT NULL,
        object_schema VARCHAR(64) NOT NULL,
        object_name VARCHAR(128) NOT NULL,
        object_type VARCHAR(32) NOT NULL,
        data_owner_upn VARCHAR(255) NOT NULL,
        data_steward_upn VARCHAR(255) NOT NULL,
        domain_code VARCHAR(32) NOT NULL,
        last_reviewed_date DATE NOT NULL,
        CONSTRAINT PK_data_owners_directory PRIMARY KEY CLUSTERED (owner_id),
        CONSTRAINT UQ_data_owners_directory_object UNIQUE (object_schema, object_name)
    );
END
GO
IF OBJECT_ID(N'dbo.audit_data_access', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.audit_data_access (
        audit_id BIGINT NOT NULL,
        accessed_at DATETIME2 NOT NULL,
        accessor_upn VARCHAR(255) NOT NULL,
        accessor_role VARCHAR(64) NULL,
        object_schema VARCHAR(64) NOT NULL,
        object_name VARCHAR(128) NOT NULL,
        operation VARCHAR(16) NOT NULL,
        rows_affected INT NULL,
        purpose_of_use VARCHAR(64) NULL,
        contains_pii BIT NOT NULL,
        CONSTRAINT PK_audit_data_access PRIMARY KEY CLUSTERED (audit_id)
    );
END
GO
PRINT 'Purview demo extensions applied successfully.';
GO
"""

PURVIEW_DEMO_SEED_SQL = r"""
SET NOCOUNT ON;
GO
IF COL_LENGTH('dbo.service_requests', 'no_show_reason_code') IS NULL
    ALTER TABLE dbo.service_requests ADD no_show_reason_code VARCHAR(64) NULL;
GO
DELETE FROM dbo.customer_complaints;
DELETE FROM dbo.customer_consents;
DELETE FROM dbo.audit_data_access;
DELETE FROM dbo.data_owners_directory;
GO
MERGE dbo.service_zones AS tgt
USING (
    VALUES
    ('CA-ON','Ontario',NULL,'ON','ranbir.singh@enercare.ca',NULL),
    ('CA-ON-GTA','Greater Toronto Area',NULL,'ON','ranbir.singh@enercare.ca',120),
    ('CA-ON-GTA-N','GTA North',NULL,'ON','mhuang@enercare.ca',90),
    ('CA-ON-GTA-S','GTA South',NULL,'ON','mhuang@enercare.ca',90),
    ('CA-ON-GTA-E','GTA East',NULL,'ON','rpatel@enercare.ca',90),
    ('CA-ON-GTA-W','GTA West',NULL,'ON','rpatel@enercare.ca',90),
    ('CA-ON-OTT','Ottawa Region',NULL,'ON','Rupal.Solanki@enercare.ca',150),
    ('CA-ON-SWO','Southwestern Ontario',NULL,'ON','Rupal.Solanki@enercare.ca',180)
) AS src(zone_code, zone_name, parent_zone_code, province, zone_manager_upn, sla_target_minutes)
ON tgt.zone_code = src.zone_code
WHEN MATCHED THEN
    UPDATE SET
        tgt.zone_name = src.zone_name,
        tgt.parent_zone_code = src.parent_zone_code,
        tgt.province = src.province,
        tgt.zone_manager_upn = src.zone_manager_upn,
        tgt.sla_target_minutes = src.sla_target_minutes
WHEN NOT MATCHED THEN
    INSERT (zone_code, zone_name, parent_zone_code, province, zone_manager_upn, sla_target_minutes)
    VALUES (src.zone_code, src.zone_name, src.parent_zone_code, src.province, src.zone_manager_upn, src.sla_target_minutes);
GO
MERGE dbo.employees AS tgt
USING (
    VALUES
    (1,'Victoria.Tan@enercare.ca','Victoria','Tan','Victoria.Tan@enercare.ca','+1-416-555-0101','Chief Customer Officer','Executive',NULL,CAST('2016-04-01' AS DATE),NULL,CAST('1976-04-22' AS DATE),'M5V',1),
    (2,'ranbir.singh@enercare.ca','Ranbir','Singh','ranbir.singh@enercare.ca','+1-416-555-0102','Enercare Leadership Data Plane','Engineering',1,CAST('2020-02-15' AS DATE),NULL,CAST('1981-03-22' AS DATE),'M4Y',1),
    (3,'Ci.Zhu@enercare.ca','Ci','Zhu','Ci.Zhu@enercare.ca','+1-437-860-6862','Senior Manager Data Strategy','Data Office',1,CAST('2021-06-07' AS DATE),NULL,CAST('1985-11-04' AS DATE),'L3R',1),
    (4,'Rupal.Solanki@enercare.ca','Rupal','Solanki','Rupal.Solanki@enercare.ca','+1-416-555-0104','Data Steward','Data Office',3,CAST('2020-09-21' AS DATE),NULL,CAST('1979-06-30' AS DATE),'M4W',1),
    (5,'Shruthi.Srinivas@enercare.ca','Shruthi','Srinivas','Shruthi.Srinivas@enercare.ca','+1-416-555-0105','Data Steward','Data Office',3,CAST('2018-01-10' AS DATE),NULL,CAST('1971-09-15' AS DATE),'L4C',1),
    (101,'tnguyen@enercare.ca','Tom','Nguyen','tnguyen@enercare.ca','+1-416-555-1101','Service Technician','Field Ops',2,CAST('2022-03-14' AS DATE),NULL,CAST('1990-04-12' AS DATE),'L6T',1),
    (102,'smehta@enercare.ca','Sneha','Mehta','smehta@enercare.ca','+1-416-555-1102','Service Technician','Field Ops',2,CAST('2021-11-01' AS DATE),NULL,CAST('1988-07-19' AS DATE),'L5N',1),
    (103,'bfontaine@enercare.ca','Benoit','Fontaine','bfontaine@enercare.ca','+1-416-555-1103','Service Technician','Field Ops',2,CAST('2020-05-08' AS DATE),NULL,CAST('1985-01-25' AS DATE),'K2H',1),
    (104,'kahmed@enercare.ca','Karim','Ahmed','kahmed@enercare.ca','+1-416-555-1104','Service Technician','Field Ops',2,CAST('2023-02-20' AS DATE),NULL,CAST('1992-12-03' AS DATE),'L1S',1),
    (105,'mhuang@enercare.ca','Mei','Huang','mhuang@enercare.ca','+1-416-555-1105','Field Supervisor','Field Ops',2,CAST('2019-08-18' AS DATE),NULL,CAST('1983-05-21' AS DATE),'L4G',1),
    (106,'rpatel@enercare.ca','Rashmi','Patel','rpatel@enercare.ca','+1-416-555-1106','Field Supervisor','Field Ops',2,CAST('2019-10-04' AS DATE),NULL,CAST('1982-09-08' AS DATE),'L8N',1)
) AS src(employee_id, upn, first_name, last_name, email, phone, role, department, manager_employee_id, hire_date, sin_full, date_of_birth, home_postal_code, is_active)
ON tgt.employee_id = src.employee_id
WHEN MATCHED THEN
    UPDATE SET
        tgt.upn = src.upn,
        tgt.first_name = src.first_name,
        tgt.last_name = src.last_name,
        tgt.email = src.email,
        tgt.phone = src.phone,
        tgt.role = src.role,
        tgt.department = src.department,
        tgt.manager_employee_id = src.manager_employee_id,
        tgt.hire_date = src.hire_date,
        tgt.date_of_birth = src.date_of_birth,
        tgt.home_postal_code = src.home_postal_code,
        tgt.is_active = src.is_active
WHEN NOT MATCHED THEN
    INSERT (employee_id, upn, first_name, last_name, email, phone, role, department, manager_employee_id, hire_date, sin_full, date_of_birth, home_postal_code, is_active)
    VALUES (src.employee_id, src.upn, src.first_name, src.last_name, src.email, src.phone, src.role, src.department, src.manager_employee_id, src.hire_date, src.sin_full, src.date_of_birth, src.home_postal_code, src.is_active);
GO
DELETE FROM dbo.billing_transactions WHERE transaction_id IN (183746223, 183746224);
DELETE FROM dbo.service_requests WHERE request_id = 2026051142;
DELETE FROM dbo.contracts WHERE contract_id = 183746222;
DELETE FROM dbo.equipment_registry WHERE equipment_id = 183746221 OR serial_number = 'LX2020-MARIA98V';
DELETE FROM dbo.service_accounts WHERE service_account_id = 183746220 OR account_number = 'EC18374622-SVC';
DELETE FROM dbo.customers WHERE customer_id = 18374622 OR account_number = 'EC18374622';
GO
INSERT INTO dbo.customers (customer_id, account_number, first_name, last_name, email, phone, customer_type, status, city, province, postal_code, created_date, date_of_birth, sin_last_4, owner_email, marketing_consent) VALUES
(18374622, 'EC18374622', 'Maria', 'Castellanos', 'maria.castellanos@example.ca', '905-555-4622', 'Residential', 'Active', 'Markham', 'ON', 'L4G 2H9', '2020-10-17', '1983-07-09', NULL, 'Rupal.Solanki@enercare.ca', 1);
GO
INSERT INTO dbo.service_accounts (service_account_id, customer_id, account_number, utility_type, rate_class, distributor, status, service_address, city, postal_code, opened_date, latitude, longitude, service_zone_code) VALUES
(183746220, 18374622, 'EC18374622-SVC', 'Natural Gas', 'Residential', 'Enbridge Gas', 'Active', '47 Birch Drive, Unit 8', 'Markham', 'L4G 2H9', '2020-10-17', 43.879200, -79.263600, 'CA-ON-GTA-N');
GO
INSERT INTO dbo.equipment_registry (equipment_id, service_account_id, equipment_type, make, model, serial_number, ownership_type, fuel_type, install_date, warranty_expiry, status) VALUES
(183746221, 183746220, 'Furnace', 'Lennox', 'SLP98V', 'LX2020-MARIA98V', 'Rental', 'Natural Gas', '2020-10-17', '2030-10-17', 'Active');
GO
INSERT INTO dbo.contracts (contract_id, service_account_id, product_id, contract_status, start_date, end_date, monthly_amount, auto_renew, cancellation_date, cancellation_reason) VALUES
(183746222, 183746220, 4, 'Active', '2020-10-17', NULL, 89.95, 1, NULL, NULL);
GO
INSERT INTO dbo.service_requests (request_id, service_account_id, equipment_id, request_type, priority, status, description, created_date, scheduled_date, completed_date, technician_id, no_show_reason_code, resolution_notes) VALUES
(2026051142, 183746220, 183746221, 'Emergency Repair', 'Emergency', 'InProgress', 'NoHeat furnace case opened through portal; scheduled pending tech after missed 24-hour SLA.', '2026-06-13', '2026-06-14', NULL, 105, 'DISPATCH_NO_REASSIGN', 'Scheduled - Pending Tech; GTA North dispatch did not reassign after the SLA breach.');
GO
INSERT INTO dbo.billing_transactions (transaction_id, contract_id, service_account_id, transaction_type, transaction_date, due_date, amount, tax_amount, payment_method, status, invoice_number, bank_routing_last_4, card_pan_last_4) VALUES
(183746223, 183746222, 183746220, 'MonthlyCharge', '2026-06-15', '2026-06-30', 89.95, 11.69, 'CreditCard', 'Posted', 'INV-MARIA-202606', '1837', '4622'),
(183746224, 183746222, 183746220, 'Credit', '2026-06-17', NULL, -14.99, 0.00, 'CreditCard', 'Posted', 'CR-MARIA-SLA-202606', '1837', '4622');
GO
UPDATE dbo.customers SET date_of_birth = COALESCE(date_of_birth, DATEADD(DAY, -((ABS(CHECKSUM(NEWID())) % 14600) + 7300), CAST(GETDATE() AS DATE))), owner_email = COALESCE(owner_email, CASE customer_id % 3 WHEN 0 THEN 'Rupal.Solanki@enercare.ca' WHEN 1 THEN 'Shruthi.Srinivas@enercare.ca' ELSE 'Ci.Zhu@enercare.ca' END), marketing_consent = COALESCE(marketing_consent, CASE WHEN customer_id % 4 = 0 THEN 0 ELSE 1 END);
GO
UPDATE dbo.service_accounts SET latitude = COALESCE(latitude, 43.4 + (ABS(CHECKSUM(NEWID())) % 700) / 1000.0), longitude = COALESCE(longitude, -79.8 + (ABS(CHECKSUM(NEWID())) % 900) / 1000.0), service_zone_code = COALESCE(service_zone_code, CASE ABS(CHECKSUM(NEWID())) % 6 WHEN 0 THEN 'CA-ON-GTA-N' WHEN 1 THEN 'CA-ON-GTA-S' WHEN 2 THEN 'CA-ON-GTA-E' WHEN 3 THEN 'CA-ON-GTA-W' WHEN 4 THEN 'CA-ON-OTT' ELSE 'CA-ON-SWO' END);
GO
UPDATE dbo.service_requests
SET no_show_reason_code = COALESCE(no_show_reason_code,
    CASE
        WHEN completed_date IS NOT NULL OR status IN ('Completed', 'Closed', 'Resolved', 'Cancelled') THEN 'NOT_APPLICABLE'
        WHEN UPPER(COALESCE(resolution_notes, '')) LIKE '%DISPATCH%REASSIGN%' OR UPPER(COALESCE(resolution_notes, '')) LIKE '%DID NOT REASSIGN%' THEN 'DISPATCH_NO_REASSIGN'
        WHEN UPPER(COALESCE(resolution_notes, '')) LIKE '%CUSTOMER NOT HOME%' OR UPPER(COALESCE(resolution_notes, '')) LIKE '%NO ANSWER AT DOOR%' THEN 'CUSTOMER_NOT_HOME'
        WHEN UPPER(COALESCE(resolution_notes, '')) LIKE '%NO TECH%' OR UPPER(COALESCE(resolution_notes, '')) LIKE '%TECH UNAVAILABLE%' OR UPPER(COALESCE(resolution_notes, '')) LIKE '%CAPACITY%' THEN 'TECH_CAPACITY_CONSTRAINT'
        WHEN UPPER(COALESCE(resolution_notes, '')) LIKE '%WEATHER%' OR UPPER(COALESCE(resolution_notes, '')) LIKE '%STORM%' THEN 'WEATHER_DELAY'
        WHEN scheduled_date IS NOT NULL AND completed_date IS NULL THEN 'CAUSE_UNSPECIFIED'
        ELSE 'NOT_APPLICABLE'
    END);
GO
UPDATE dbo.billing_transactions SET bank_routing_last_4 = COALESCE(bank_routing_last_4, RIGHT('0000' + CAST(ABS(CHECKSUM(NEWID())) % 10000 AS VARCHAR(4)), 4)), card_pan_last_4 = COALESCE(card_pan_last_4, RIGHT('0000' + CAST(ABS(CHECKSUM(NEWID())) % 10000 AS VARCHAR(4)), 4));
GO
;WITH n AS (SELECT TOP (30) ROW_NUMBER() OVER (ORDER BY (SELECT NULL)) AS rn FROM sys.objects), consent_types AS (SELECT 1 AS k, 'Marketing-Email' AS t, 'CASL' AS lb UNION ALL SELECT 2,'Marketing-SMS','CASL' UNION ALL SELECT 3,'Data-Sharing','PIPEDA' UNION ALL SELECT 4,'Retention','PIPEDA')
INSERT INTO dbo.customer_consents (consent_id, customer_id, consent_type, consent_status, legal_basis, granted_date, withdrawn_date, source_channel, captured_by_upn)
SELECT (n.rn - 1) * 4 + ct.k, n.rn, ct.t, CASE WHEN (n.rn + ct.k) % 5 = 0 THEN 'Withdrawn' ELSE 'Granted' END, ct.lb, DATEADD(DAY, -((n.rn * 7 + ct.k * 13) % 800), CAST(GETDATE() AS DATE)), NULL, 'CallCenter', 'Rupal.Solanki@enercare.ca' FROM n CROSS JOIN consent_types ct;
GO
INSERT INTO dbo.customer_consents (consent_id, customer_id, consent_type, consent_status, legal_basis, granted_date, withdrawn_date, source_channel, captured_by_upn) VALUES
(183746221, 18374622, 'Marketing-Email', 'Granted', 'CASL', '2026-06-17', NULL, 'CallCenter', 'tnguyen@enercare.ca'),
(183746222, 18374622, 'Marketing-SMS', 'Granted', 'CASL', '2026-06-17', NULL, 'CallCenter', 'tnguyen@enercare.ca'),
(183746223, 18374622, 'Data-Sharing', 'Granted', 'PIPEDA', '2026-06-17', NULL, 'CallCenter', 'tnguyen@enercare.ca'),
(183746224, 18374622, 'Retention', 'Granted', 'PIPEDA', '2026-06-17', NULL, 'CallCenter', 'tnguyen@enercare.ca');
GO
;WITH n AS (SELECT TOP (18) ROW_NUMBER() OVER (ORDER BY (SELECT NULL)) AS rn FROM sys.objects)
INSERT INTO dbo.customer_complaints (complaint_id, customer_id, service_account_id, complaint_type, severity, opened_date, closed_date, status, assigned_to_upn, description, regulator_case_ref)
SELECT rn, ((rn * 3) % 50) + 1, NULL, CASE rn % 4 WHEN 0 THEN 'Privacy' WHEN 1 THEN 'Billing' WHEN 2 THEN 'Service' ELSE 'AutoRenew' END, CASE WHEN rn IN (3, 7, 15) THEN 'RegulatorReportable' WHEN rn % 3 = 0 THEN 'High' ELSE 'Medium' END, DATEADD(DAY, -rn, CAST(GETDATE() AS DATE)), NULL, CASE WHEN rn % 3 = 0 THEN 'Escalated' ELSE 'Resolved' END, 'Rupal.Solanki@enercare.ca', CONCAT('Synthetic complaint ', rn), CASE WHEN rn IN (3, 7, 15) THEN CONCAT('REG-2026-', RIGHT(CONCAT('0000', rn), 4)) ELSE NULL END FROM n;
GO
INSERT INTO dbo.customer_complaints (complaint_id, customer_id, service_account_id, complaint_type, severity, opened_date, closed_date, status, assigned_to_upn, description, regulator_case_ref) VALUES
(18374622, 18374622, 183746220, 'Service', 'High', '2026-06-17', NULL, 'Escalated', 'tnguyen@enercare.ca', 'NoHeat furnace request missed the 24-hour SLA in GTA North; customer was still billed monthly rental charge.', NULL);
GO
INSERT INTO dbo.data_owners_directory (owner_id, object_schema, object_name, object_type, data_owner_upn, data_steward_upn, domain_code, last_reviewed_date) VALUES
(1,'dbo','customers','Table','Victoria.Tan@enercare.ca','Rupal.Solanki@enercare.ca','DOM-CUSTOPS','2026-05-20'),(2,'dbo','service_accounts','Table','Victoria.Tan@enercare.ca','Rupal.Solanki@enercare.ca','DOM-CUSTOPS','2026-05-20'),(3,'dbo','customer_consents','Table','Victoria.Tan@enercare.ca','Victoria.Tan@enercare.ca','DOM-CUSTOPS','2026-05-20'),(4,'dbo','customer_complaints','Table','Victoria.Tan@enercare.ca','Rupal.Solanki@enercare.ca','DOM-CUSTOPS','2026-05-20'),(5,'dbo','employees','Table','Victoria.Tan@enercare.ca','Victoria.Tan@enercare.ca','DOM-CUSTOPS','2026-05-20'),(6,'dbo','equipment_registry','Table','ranbir.singh@enercare.ca','Shruthi.Srinivas@enercare.ca','DOM-SVCDEL','2026-05-20'),(7,'dbo','service_requests','Table','ranbir.singh@enercare.ca','Shruthi.Srinivas@enercare.ca','DOM-SVCDEL','2026-05-20'),(8,'dbo','service_zones','Table','ranbir.singh@enercare.ca','Shruthi.Srinivas@enercare.ca','DOM-SVCDEL','2026-05-20'),(9,'dbo','products','Table','Ci.Zhu@enercare.ca','Ci.Zhu@enercare.ca','DOM-REVCON','2026-05-20'),(10,'dbo','contracts','Table','Ci.Zhu@enercare.ca','Ci.Zhu@enercare.ca','DOM-REVCON','2026-05-20'),(11,'dbo','billing_transactions','Table','Ci.Zhu@enercare.ca','Ci.Zhu@enercare.ca','DOM-REVCON','2026-05-20'),(12,'dbo','data_owners_directory','Table','Ci.Zhu@enercare.ca','Ci.Zhu@enercare.ca','DOM-CUSTOPS','2026-05-20'),(13,'dbo','audit_data_access','Table','Ci.Zhu@enercare.ca','Ci.Zhu@enercare.ca','DOM-CUSTOPS','2026-05-20');
GO
;WITH n AS (SELECT TOP (200) ROW_NUMBER() OVER (ORDER BY (SELECT NULL)) AS rn FROM sys.objects a CROSS JOIN sys.objects b)
INSERT INTO dbo.audit_data_access (audit_id, accessed_at, accessor_upn, accessor_role, object_schema, object_name, operation, rows_affected, purpose_of_use, contains_pii)
SELECT rn, DATEADD(HOUR, -rn, SYSUTCDATETIME()), CASE rn % 5 WHEN 0 THEN 'Victoria.Tan@enercare.ca' WHEN 1 THEN 'Ci.Zhu@enercare.ca' WHEN 2 THEN 'Rupal.Solanki@enercare.ca' WHEN 3 THEN 'Shruthi.Srinivas@enercare.ca' ELSE 'ranbir.singh@enercare.ca' END, 'Data Reader', 'dbo', CASE rn % 6 WHEN 0 THEN 'customers' WHEN 1 THEN 'service_accounts' WHEN 2 THEN 'billing_transactions' WHEN 3 THEN 'customer_consents' WHEN 4 THEN 'service_requests' ELSE 'contracts' END, 'SELECT', 1 + (rn % 100), CASE rn % 4 WHEN 0 THEN 'BillingSupport' WHEN 1 THEN 'RegulatorReport' WHEN 2 THEN 'MarketingCampaign' ELSE 'DataScience' END, CASE WHEN rn % 6 IN (0, 1, 2, 3) THEN 1 ELSE 0 END FROM n;
GO
INSERT INTO dbo.audit_data_access (audit_id, accessed_at, accessor_upn, accessor_role, object_schema, object_name, operation, rows_affected, purpose_of_use, contains_pii) VALUES
(1837462201, DATEADD(MINUTE, -12, SYSUTCDATETIME()), 'tnguyen@enercare.ca', 'CustomerService', 'dbo', 'customers', 'SELECT', 1, 'CustomerService', 1),
(1837462202, DATEADD(MINUTE, -11, SYSUTCDATETIME()), 'tnguyen@enercare.ca', 'CustomerService', 'dbo', 'customer_consents', 'SELECT', 4, 'CustomerService', 1),
(1837462203, DATEADD(MINUTE, -10, SYSUTCDATETIME()), 'tnguyen@enercare.ca', 'CustomerService', 'dbo', 'service_requests', 'SELECT', 1, 'CustomerService', 0),
(1837462204, DATEADD(MINUTE, -9, SYSUTCDATETIME()), 'tnguyen@enercare.ca', 'CustomerService', 'dbo', 'billing_transactions', 'SELECT', 2, 'CustomerService', 1);
GO
PRINT 'Purview demo seed complete.';
GO
"""

PURVIEW_METADATA_SCHEMA_SQL = r"""
SET NOCOUNT ON;
GO
IF OBJECT_ID(N'dbo.governance_domains', N'U') IS NULL CREATE TABLE dbo.governance_domains (domain_id VARCHAR(64) NOT NULL, domain_name NVARCHAR(200) NOT NULL, domain_type VARCHAR(64) NOT NULL, description NVARCHAR(1000) NULL, parent_domain VARCHAR(64) NULL, status VARCHAR(32) NOT NULL, governance_domain_owners NVARCHAR(1000) NULL, governance_domain_creators NVARCHAR(1000) NULL, CONSTRAINT PK_governance_domains PRIMARY KEY CLUSTERED (domain_id));
GO
IF OBJECT_ID(N'dbo.governance_data_products', N'U') IS NULL CREATE TABLE dbo.governance_data_products (data_product_id VARCHAR(64) NOT NULL, data_product_name NVARCHAR(200) NOT NULL, product_type VARCHAR(64) NOT NULL, business_use_case NVARCHAR(1000) NULL, audience NVARCHAR(400) NULL, owners NVARCHAR(1000) NULL, attached_assets NVARCHAR(MAX) NULL, access_policy NVARCHAR(MAX) NULL, status VARCHAR(32) NOT NULL, parent_domain_id VARCHAR(64) NOT NULL, CONSTRAINT PK_governance_data_products PRIMARY KEY CLUSTERED (data_product_id));
GO
IF OBJECT_ID(N'dbo.governance_glossary_terms', N'U') IS NULL CREATE TABLE dbo.governance_glossary_terms (term_code VARCHAR(64) NOT NULL, term_name NVARCHAR(200) NOT NULL, acronyms NVARCHAR(200) NULL, parent_term_code VARCHAR(64) NULL, domain_code VARCHAR(64) NULL, owner_upn VARCHAR(255) NULL, additional_owners_upn NVARCHAR(1000) NULL, definition NVARCHAR(MAX) NOT NULL, status VARCHAR(32) NOT NULL, is_cde BIT NOT NULL, industry_origin VARCHAR(64) NULL, resources NVARCHAR(MAX) NULL, bound_assets NVARCHAR(MAX) NULL, CONSTRAINT PK_governance_glossary_terms PRIMARY KEY CLUSTERED (term_code));
GO
IF OBJECT_ID(N'dbo.governance_cdes', N'U') IS NULL CREATE TABLE dbo.governance_cdes (cde_id VARCHAR(64) NOT NULL, cde_name NVARCHAR(200) NOT NULL, expected_data_type VARCHAR(32) NOT NULL, business_definition NVARCHAR(MAX) NOT NULL, owner_role VARCHAR(128) NULL, status VARCHAR(32) NOT NULL, parent_glossary_term VARCHAR(64) NULL, bound_columns NVARCHAR(MAX) NULL, CONSTRAINT PK_governance_cdes PRIMARY KEY CLUSTERED (cde_id));
GO
IF OBJECT_ID(N'dbo.governance_role_assignments', N'U') IS NULL CREATE TABLE dbo.governance_role_assignments (role_id VARCHAR(64) NOT NULL, principal_email VARCHAR(255) NOT NULL, principal_display_name NVARCHAR(200) NOT NULL, role_type VARCHAR(128) NOT NULL, scope_target NVARCHAR(300) NOT NULL, scope_target_type VARCHAR(64) NOT NULL, governance_layer VARCHAR(64) NOT NULL, CONSTRAINT PK_governance_role_assignments PRIMARY KEY CLUSTERED (role_id));
GO
IF OBJECT_ID(N'dbo.governance_label_assignments', N'U') IS NULL CREATE TABLE dbo.governance_label_assignments (label_id VARCHAR(64) NOT NULL, label_name NVARCHAR(200) NOT NULL, sensitivity_tier VARCHAR(64) NOT NULL, protection_policy NVARCHAR(MAX) NULL, applies_to_asset_ids NVARCHAR(MAX) NULL, scope VARCHAR(128) NOT NULL, CONSTRAINT PK_governance_label_assignments PRIMARY KEY CLUSTERED (label_id));
GO
PRINT 'Purview metadata schema tables are ready.';
GO
"""

PURVIEW_METADATA_SEED_SQL = r"""
SET NOCOUNT ON;
GO
-- Clear the OKR tables first (sql/11_ontology_okr_schema.sql), which FK-reference
-- governance_domains/governance_data_products and are not owned by this notebook.
-- Re-run sql/12_seed_ontology_okrs.sql afterward to restore OKRs and their links.
IF OBJECT_ID(N'dbo.governance_okr_data_products', N'U') IS NOT NULL DELETE FROM dbo.governance_okr_data_products;
IF OBJECT_ID(N'dbo.governance_okr_key_results', N'U') IS NOT NULL DELETE FROM dbo.governance_okr_key_results;
IF OBJECT_ID(N'dbo.governance_okrs', N'U') IS NOT NULL DELETE FROM dbo.governance_okrs;
DELETE FROM dbo.governance_label_assignments; DELETE FROM dbo.governance_role_assignments; DELETE FROM dbo.governance_cdes; DELETE FROM dbo.governance_glossary_terms; DELETE FROM dbo.governance_data_products; DELETE FROM dbo.governance_domains;
GO
INSERT INTO dbo.governance_domains (domain_id, domain_name, domain_type, description, parent_domain, status, governance_domain_owners, governance_domain_creators) VALUES ('DOM-CUSTOPS','Customer Operations','Data domain','Customer support, consent, complaint, and profile stewardship domain.',NULL,'Published','Victoria.Tan@enercare.ca;Ci.Zhu@enercare.ca','Ci.Zhu@enercare.ca;Alison.Pouw@microsoft.com'),('DOM-SVCDEL','Service Delivery','Data domain','Field service scheduling, work-order execution, and SLA governance.',NULL,'Published','ranbir.singh@enercare.ca;Ci.Zhu@enercare.ca','Ci.Zhu@enercare.ca;Alison.Pouw@microsoft.com'),('DOM-REVCON','Revenue and Contracts','Data domain','Billing, contracts, renewals, and financial governance domain.',NULL,'Published','Ci.Zhu@enercare.ca;ranbir.singh@enercare.ca','Ci.Zhu@enercare.ca;Alison.Pouw@microsoft.com');
GO
INSERT INTO dbo.governance_data_products (data_product_id, data_product_name, product_type, business_use_case, audience, owners, attached_assets, access_policy, status, parent_domain_id) VALUES ('DP-CUST360','Customer 360','Master and reference data','Single customer profile and consent posture for call-center and compliance operations.','Call Center;Privacy;Leadership','Victoria.Tan@enercare.ca','dbo.customers;dbo.customer_consents;BrookfieldEnercare/dim_customer','Role-based access with privacy approval for regulated attributes.','Published','DOM-CUSTOPS'),('DP-SVCPERF','Service Performance','Dataset','Track service request performance, technician throughput, and SLA adherence.','Field Operations;Leadership','ranbir.singh@enercare.ca','dbo.service_requests;dbo.service_accounts;dbo.service_zones;BrookfieldEnercare/fct_service_requests','Operational use for service planning and SLA management.','Published','DOM-SVCDEL'),('DP-BILLHEALTH','Billing Health','Dataset','Monitor billing accuracy, repeat complaints, and contract renewal outcomes.','Finance;Customer Care;Leadership','Ci.Zhu@enercare.ca','dbo.billing_transactions;dbo.contracts;dbo.customer_complaints;BrookfieldEnercare/fct_billing','Access requires finance and governance approval for sensitive fields.','Published','DOM-REVCON');
GO
;WITH n AS (SELECT TOP (35) ROW_NUMBER() OVER (ORDER BY (SELECT NULL)) AS rn FROM sys.objects)
INSERT INTO dbo.governance_glossary_terms (term_code, term_name, acronyms, parent_term_code, domain_code, owner_upn, additional_owners_upn, definition, status, is_cde, industry_origin, resources, bound_assets)
SELECT CONCAT('GT-', RIGHT(CONCAT('000', rn), 3)), CASE rn WHEN 1 THEN 'Customer' WHEN 2 THEN 'Social Insurance Number' WHEN 3 THEN 'Customer Consent' WHEN 4 THEN 'PCI Scope Data' WHEN 5 THEN 'Service Request' WHEN 6 THEN 'First Contact Resolution' WHEN 7 THEN 'Contract' WHEN 8 THEN 'Billing Transaction' WHEN 9 THEN 'Data Owner' WHEN 10 THEN 'Data Access Audit' ELSE CONCAT('Governance Term ', rn) END, CASE rn WHEN 2 THEN 'SIN' WHEN 4 THEN 'PCI' WHEN 6 THEN 'FCR' ELSE NULL END, NULL, CASE rn % 3 WHEN 0 THEN 'DOM-REVCON' WHEN 1 THEN 'DOM-CUSTOPS' ELSE 'DOM-SVCDEL' END, 'Ci.Zhu@enercare.ca', 'Victoria.Tan@enercare.ca', CONCAT('Notebook-owned governance term definition ', rn), 'Published', CASE WHEN rn <= 12 THEN 1 ELSE 0 END, 'Generic', 'internal://glossary/notebook', CASE rn WHEN 1 THEN 'dbo.customers.customer_id' WHEN 2 THEN 'dbo.employees.sin_full;dbo.customers.sin_last_4' WHEN 3 THEN 'dbo.customer_consents' WHEN 4 THEN 'dbo.billing_transactions.card_pan_last_4;dbo.billing_transactions.bank_routing_last_4' WHEN 5 THEN 'dbo.service_requests' WHEN 6 THEN 'BrookfieldEnercare/_Measures/FCR' ELSE 'dbo.customers;dbo.service_requests' END FROM n;
GO
INSERT INTO dbo.governance_cdes (cde_id, cde_name, expected_data_type, business_definition, owner_role, status, parent_glossary_term, bound_columns) VALUES ('CDE-CUST-ID','Customer Identifier','number','Unique enterprise identifier for customer entities.','Data Steward','Published','GT-001','dbo.customers.customer_id'),('CDE-SVCACCT-ID','Service Account Identifier','number','Unique identifier for service account records.','Data Steward','Published','GT-005','dbo.service_accounts.service_account_id'),('CDE-CONTRACT-ID','Contract Identifier','number','Unique identifier for customer contracts.','Data Steward','Published','GT-007','dbo.contracts.contract_id'),('CDE-REQ-ID','Service Request Identifier','number','Unique service request key.','Data Steward','Published','GT-005','dbo.service_requests.request_id'),('CDE-CONSENT-STATUS','Consent Status','text','Current legal status of customer consent record.','Privacy Officer','Published','GT-003','dbo.customer_consents.consent_status'),('CDE-SIN','Social Insurance Number','text','Canadian SIN full or partial representation.','Privacy Officer','Published','GT-002','dbo.employees.sin_full;dbo.customers.sin_last_4'),('CDE-DOB','Date Of Birth','date','Customer date of birth for identity and eligibility checks.','Privacy Officer','Published','GT-001','dbo.customers.date_of_birth'),('CDE-GEO','Geo Coordinates','text','Service account latitude and longitude values.','Data Steward','Published','GT-001','dbo.service_accounts.latitude;dbo.service_accounts.longitude'),('CDE-PAN-LAST4','Card PAN Last 4','text','Last four digits of payment card number.','Finance Steward','Published','GT-004','dbo.billing_transactions.card_pan_last_4'),('CDE-BANK-LAST4','Bank Routing Last 4','text','Last four digits of bank routing details.','Finance Steward','Published','GT-004','dbo.billing_transactions.bank_routing_last_4'),('CDE-OWNER-UPN','Data Owner UPN','text','UPN of assigned data owner for governed object.','Data Governance Admin','Published','GT-009','dbo.data_owners_directory.data_owner_upn'),('CDE-AUDIT-PURPOSE','Audit Purpose Of Use','text','Declared purpose for data access event.','Data Governance Admin','Published','GT-010','dbo.audit_data_access.purpose_of_use');
GO
;WITH n AS (SELECT TOP (48) ROW_NUMBER() OVER (ORDER BY (SELECT NULL)) AS rn FROM sys.objects)
INSERT INTO dbo.governance_role_assignments (role_id, principal_email, principal_display_name, role_type, scope_target, scope_target_type, governance_layer)
SELECT CONCAT('R', RIGHT(CONCAT('000', rn), 3)), CASE rn % 6 WHEN 0 THEN 'seankelley@microsoft.com' WHEN 1 THEN 'Ci.Zhu@enercare.ca' WHEN 2 THEN 'Victoria.Tan@enercare.ca' WHEN 3 THEN 'ranbir.singh@enercare.ca' WHEN 4 THEN 'Rupal.Solanki@enercare.ca' ELSE 'Shruthi.Srinivas@enercare.ca' END, CONCAT('Governance Principal ', rn), CASE rn % 5 WHEN 0 THEN 'Data Governance Administrator' WHEN 1 THEN 'Governance Domain Owner' WHEN 2 THEN 'Data Product Owner' WHEN 3 THEN 'Data Steward' ELSE 'Global Catalog Reader' END, CASE rn % 4 WHEN 0 THEN 'Enercare' WHEN 1 THEN 'DOM-CUSTOPS' WHEN 2 THEN 'DOM-SVCDEL' ELSE 'DOM-REVCON' END, CASE WHEN rn % 4 = 0 THEN 'Collection' ELSE 'Domain' END, CASE WHEN rn % 4 = 0 THEN 'Tenant' ELSE 'Domain' END FROM n;
GO
;WITH n AS (SELECT TOP (9) ROW_NUMBER() OVER (ORDER BY (SELECT NULL)) AS rn FROM sys.objects)
INSERT INTO dbo.governance_label_assignments (label_id, label_name, sensitivity_tier, protection_policy, applies_to_asset_ids, scope)
SELECT CONCAT('LBL-', RIGHT(CONCAT('000', rn), 3)), CASE rn WHEN 1 THEN 'General' WHEN 2 THEN 'Internal' WHEN 3 THEN 'Confidential' WHEN 4 THEN 'Highly Confidential' WHEN 5 THEN 'PCI Restricted' WHEN 6 THEN 'Privacy Restricted' WHEN 7 THEN 'Operations Sensitive' WHEN 8 THEN 'Executive KPI' ELSE 'Governance Admin' END, CASE WHEN rn IN (4,5,6) THEN 'Highly Confidential' WHEN rn IN (3,7,9) THEN 'Confidential' WHEN rn = 1 THEN 'General' ELSE 'Internal' END, 'Notebook-owned policy seed.', CASE rn WHEN 4 THEN 'dbo.employees.sin_full;dbo.customers.sin_last_4' WHEN 5 THEN 'dbo.billing_transactions.card_pan_last_4' ELSE 'dbo.customers;BrookfieldEnercare.SemanticModel' END, 'Tenant' FROM n;
GO
PRINT 'Purview SQL-first metadata seed complete.';
GO
"""

print("B0A complete. SQL scripts are defined inline in this notebook; no Lakehouse Files upload is required.")


# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# CELL B1 — Execute notebook-owned Purview demo extension DDL


def split_sql_batches(script: str) -> list[str]:
    batches = []
    current = []
    for line in script.splitlines():
        if line.strip().upper() == "GO":
            batch = "\n".join(current).strip()
            if batch:
                batches.append(batch)
            current = []
        else:
            current.append(line)
    tail = "\n".join(current).strip()
    if tail:
        batches.append(tail)
    return batches


if DEMO_MODE:
    print("[DRY RUN] Skipping notebook-owned Purview demo extension DDL")
else:
    batches = split_sql_batches(PURVIEW_DEMO_EXTENSIONS_SQL)
    print(f"DDL script: {len(batches)} batches to execute")

    cur = conn.cursor()
    batch_errors = []
    for i, batch in enumerate(batches, 1):
        try:
            cur.execute(batch)
            conn.commit()
        except Exception as e:
            conn.rollback()
            message = f"Batch {i}/{len(batches)} failed: {type(e).__name__}: {e}"
            batch_errors.append(message)
            print(f"  {message}")

    if batch_errors:
        raise RuntimeError("DDL execution failed; see batch errors above.")

    print("DDL applied: notebook-owned Purview demo extensions")


# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# CELL B2 — Verify DDL applied

verify_ddl_sql = """
SELECT 'new tables present'                    AS check_name,
       COUNT(*)                                AS count_actual,
       6                                       AS count_expected
  FROM sys.tables
 WHERE name IN ('employees','service_zones','customer_consents',
                'customer_complaints','data_owners_directory','audit_data_access')
UNION ALL
SELECT 'customers PII columns added',
       CASE WHEN COL_LENGTH('dbo.customers','date_of_birth')   IS NOT NULL
              AND COL_LENGTH('dbo.customers','sin_last_4')     IS NOT NULL
              AND COL_LENGTH('dbo.customers','owner_email')    IS NOT NULL
              AND COL_LENGTH('dbo.customers','marketing_consent') IS NOT NULL
            THEN 4 ELSE 0 END,
       4
UNION ALL
SELECT 'service_accounts GPS columns added',
       CASE WHEN COL_LENGTH('dbo.service_accounts','latitude')          IS NOT NULL
              AND COL_LENGTH('dbo.service_accounts','longitude')         IS NOT NULL
              AND COL_LENGTH('dbo.service_accounts','service_zone_code') IS NOT NULL
            THEN 3 ELSE 0 END,
       3
UNION ALL
SELECT 'billing_transactions payment partials added',
       CASE WHEN COL_LENGTH('dbo.billing_transactions','bank_routing_last_4') IS NOT NULL
              AND COL_LENGTH('dbo.billing_transactions','card_pan_last_4')    IS NOT NULL
            THEN 2 ELSE 0 END,
       2;
"""

if DEMO_MODE:
    print("[DRY RUN] Skipping DDL verification query.")
else:
    cur.execute(verify_ddl_sql)
    rows = cur.fetchall()
    print(f"\n{'check_name':45s} {'actual':>8s} {'expected':>10s}  status")
    print("-" * 80)
    for r in rows:
        status = "GREEN" if r[1] == r[2] else "RED"
        print(f"{r[0]:45s} {r[1]:>8d} {r[2]:>10d}  {status}")


# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# CELL B3 — Execute notebook-owned Purview demo seed data

if DEMO_MODE:
    print("[DRY RUN] Skipping notebook-owned Purview demo seed data")
else:
    batches = split_sql_batches(PURVIEW_DEMO_SEED_SQL)
    print(f"Seed script: {len(batches)} batches to execute")

    cur = conn.cursor()
    batch_errors = []
    for i, batch in enumerate(batches, 1):
        try:
            cur.execute(batch)
            conn.commit()
        except Exception as e:
            conn.rollback()
            message = f"Batch {i}/{len(batches)} failed: {type(e).__name__}: {e}"
            batch_errors.append(message)
            print(f"  {message}")

    if batch_errors:
        raise RuntimeError("Seed execution failed; see batch errors above.")

    print("Seed applied: notebook-owned Purview demo seed data")


# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# CELL B4 — Verify seed counts

verify_seed_sql = """
SELECT 'employees'              AS table_name, COUNT(*) AS row_count, 11  AS expected FROM dbo.employees
UNION ALL
SELECT 'service_zones',                        COUNT(*),                8      FROM dbo.service_zones
UNION ALL
SELECT 'customer_consents',                    COUNT(*),              124      FROM dbo.customer_consents
UNION ALL
SELECT 'customer_complaints',                  COUNT(*),               19      FROM dbo.customer_complaints
UNION ALL
SELECT 'data_owners_directory',                COUNT(*),               13      FROM dbo.data_owners_directory
UNION ALL
SELECT 'audit_data_access',                    COUNT(*),              204      FROM dbo.audit_data_access
UNION ALL
SELECT 'customers with DOB backfilled',        COUNT(*),               51      FROM dbo.customers
 WHERE date_of_birth IS NOT NULL
UNION ALL
SELECT 'service_accounts with GPS backfilled', COUNT(*),               57      FROM dbo.service_accounts
 WHERE latitude IS NOT NULL;
"""

verify_maria_sql = """
SELECT 'Maria customer row' AS check_name, COUNT(*) AS count_actual, 1 AS count_expected
    FROM dbo.customers
 WHERE customer_id = 18374622 AND account_number = 'EC18374622'
UNION ALL
SELECT 'Maria service account row', COUNT(*), 1
    FROM dbo.service_accounts
 WHERE service_account_id = 183746220 AND customer_id = 18374622 AND service_zone_code = 'CA-ON-GTA-N'
UNION ALL
SELECT 'Maria furnace row', COUNT(*), 1
    FROM dbo.equipment_registry
 WHERE equipment_id = 183746221 AND service_account_id = 183746220 AND make = 'Lennox' AND model = 'SLP98V'
UNION ALL
SELECT 'Maria service request row', COUNT(*), 1
    FROM dbo.service_requests
 WHERE request_id = 2026051142 AND service_account_id = 183746220 AND equipment_id = 183746221
UNION ALL
SELECT 'Maria billing rows', COUNT(*), 2
    FROM dbo.billing_transactions
 WHERE service_account_id = 183746220
UNION ALL
SELECT 'Maria consent rows', COUNT(*), 4
    FROM dbo.customer_consents
 WHERE customer_id = 18374622
UNION ALL
SELECT 'Maria complaint row', COUNT(*), 1
    FROM dbo.customer_complaints
 WHERE complaint_id = 18374622 AND customer_id = 18374622
UNION ALL
SELECT 'Maria audit rows', COUNT(*), 4
    FROM dbo.audit_data_access
 WHERE audit_id BETWEEN 1837462201 AND 1837462204;
"""

if DEMO_MODE:
    print("[DRY RUN] Skipping seed verification query.")
else:
    cur.execute(verify_seed_sql)
    rows = cur.fetchall()
    print(f"\n{'table_name':45s} {'rows':>8s} {'expected':>10s}  status")
    print("-" * 80)
    for r in rows:
        status = "GREEN" if r[1] == r[2] else "YELLOW"
        print(f"{r[0]:45s} {r[1]:>8d} {r[2]:>10d}  {status}")

    cur.execute(verify_maria_sql)
    rows = cur.fetchall()
    print(f"\n{'maria_check':45s} {'actual':>8s} {'expected':>10s}  status")
    print("-" * 80)
    for r in rows:
        status = "GREEN" if r[1] == r[2] else "YELLOW"
        print(f"{r[0]:45s} {r[1]:>8d} {r[2]:>10d}  {status}")


# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# CELL B4A — Execute notebook-owned SQL-first metadata schema and seed


def execute_sql_script(sql_script: str, friendly_name: str) -> None:
    batches = split_sql_batches(sql_script)
    print(f"{friendly_name}: {len(batches)} batches to execute")

    local_cur = conn.cursor()
    batch_errors = []
    for i, batch in enumerate(batches, 1):
        try:
            local_cur.execute(batch)
            conn.commit()
        except Exception as e:
            conn.rollback()
            message = f"Batch {i}/{len(batches)} failed: {type(e).__name__}: {e}"
            batch_errors.append(message)
            print(f"  {message}")

    if batch_errors:
        raise RuntimeError(f"{friendly_name} execution failed; see batch errors above.")


if DEMO_MODE:
    print("[DRY RUN] Skipping notebook-owned metadata schema/seed execution")
else:
    execute_sql_script(PURVIEW_METADATA_SCHEMA_SQL, "Metadata schema")
    print("DDL applied: notebook-owned Purview metadata schema")

    execute_sql_script(PURVIEW_METADATA_SEED_SQL, "Metadata seed")
    print("Seed applied: notebook-owned Purview metadata seed")


# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# CELL B4B — Verify SQL-first metadata row counts

verify_metadata_sql = """
SELECT 'governance_domains'          AS table_name, COUNT(*) AS row_count,  3 AS expected FROM dbo.governance_domains
UNION ALL
SELECT 'governance_data_products',                    COUNT(*),              3               FROM dbo.governance_data_products
UNION ALL
SELECT 'governance_glossary_terms',                   COUNT(*),             35               FROM dbo.governance_glossary_terms
UNION ALL
SELECT 'governance_cdes',                             COUNT(*),             12               FROM dbo.governance_cdes
UNION ALL
SELECT 'governance_role_assignments',                 COUNT(*),             48               FROM dbo.governance_role_assignments
UNION ALL
SELECT 'governance_label_assignments',                COUNT(*),              9               FROM dbo.governance_label_assignments;
"""

if DEMO_MODE:
    print("[DRY RUN] Skipping metadata row count verification.")
else:
    cur.execute(verify_metadata_sql)
    rows = cur.fetchall()
    print(f"\n{'table_name':45s} {'rows':>8s} {'expected':>10s}  status")
    print("-" * 80)
    for r in rows:
        status = "GREEN" if r[1] == r[2] else "YELLOW"
        print(f"{r[0]:45s} {r[1]:>8d} {r[2]:>10d}  {status}")


# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# CELL B5 — Backfill Luhn-valid SIN fields

import sys
import random

TOOLS_PATH = "/lakehouse/default/Files/tools"
if TOOLS_PATH not in sys.path:
    sys.path.insert(0, TOOLS_PATH)

try:
    from sin_luhn_generator import generate_synthetic_sin, hyphenated, is_luhn_valid  # noqa: E402
    print("Using sin_luhn_generator from Lakehouse Files/tools.")
except Exception:
    print("Optional sin_luhn_generator not found in Lakehouse Files/tools; using built-in notebook SIN helper fallback.")

    def _digits(value: str) -> str:
        return "".join(ch for ch in str(value) if ch.isdigit())

    def _luhn_check_digit(eight_digits: str) -> str:
        total = 0
        for i, ch in enumerate(reversed(eight_digits), start=1):
            n = int(ch)
            if i % 2 == 1:
                n *= 2
                if n > 9:
                    n -= 9
            total += n
        return str((10 - (total % 10)) % 10)

    def is_luhn_valid(sin_value: str) -> bool:
        digits = _digits(sin_value)
        if len(digits) != 9:
            return False
        return _luhn_check_digit(digits[:8]) == digits[8]

    def generate_synthetic_sin(first_digit: str = "9", rng: random.Random | None = None) -> str:
        rng = rng or random.Random()
        prefix = first_digit if first_digit and first_digit.isdigit() else "9"
        body = "".join(str(rng.randint(0, 9)) for _ in range(7))
        first_eight = f"{prefix}{body}"
        return first_eight + _luhn_check_digit(first_eight)

    def hyphenated(sin_value: str) -> str:
        digits = _digits(sin_value)
        return f"{digits[0:3]}-{digits[3:6]}-{digits[6:9]}"

if DEMO_MODE:
    print("[DRY RUN] Skipping SIN backfill updates.")
else:
    rng = random.Random(20260605)

    cur.execute("SELECT employee_id FROM dbo.employees WHERE sin_full IS NULL")
    emp_ids = [row[0] for row in cur.fetchall()]
    print(f"Backfilling sin_full for {len(emp_ids)} employees...")

    for emp_id in emp_ids:
        sin9 = generate_synthetic_sin(first_digit="9", rng=rng)
        cur.execute(
            "UPDATE dbo.employees SET sin_full = ? WHERE employee_id = ?",
            hyphenated(sin9), emp_id,
        )
    conn.commit()
    print(f"  employees.sin_full populated: {len(emp_ids)} rows")

    cur.execute("SELECT customer_id FROM dbo.customers WHERE sin_last_4 IS NULL")
    cust_ids = [row[0] for row in cur.fetchall()]
    print(f"Backfilling sin_last_4 for {len(cust_ids)} customers...")

    for cust_id in cust_ids:
        sin9 = generate_synthetic_sin(first_digit="9", rng=rng)
        cur.execute(
            "UPDATE dbo.customers SET sin_last_4 = ? WHERE customer_id = ?",
            sin9[-4:], cust_id,
        )
    conn.commit()
    print(f"  customers.sin_last_4 populated: {len(cust_ids)} rows")


# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# CELL B6 — Spot-check SIN Luhn validity

if DEMO_MODE:
    print("[DRY RUN] Skipping SIN validity spot-check.")
else:
    cur.execute("SELECT TOP 5 employee_id, sin_full FROM dbo.employees ORDER BY NEWID()")
    samples = cur.fetchall()

    print("\nSIN Luhn validation spot-check (Layer 1 backstop):")
    print(f"{'employee_id':>12s}  {'sin_full':>15s}  result")
    print("-" * 45)
    all_valid = True
    for emp_id, sin_full in samples:
        valid = is_luhn_valid(sin_full)
        all_valid = all_valid and valid
        print(f"{emp_id:>12d}  {sin_full:>15s}  {'GREEN' if valid else 'RED'}")

    print(f"\nOverall: {'ALL GREEN — Layer 1 backstop ready' if all_valid else 'RED — investigate generator'}")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# CELL B7 — Grant the Purview managed identity read access (one-time admin step)
#
# Run this cell manually, once, after approving the Purview managed private endpoint
# (enercareSqlPE) on this SQL server. Requires this notebook's identity to have
# CONTROL/ALTER ANY USER rights on the database (same identity used elsewhere in this
# notebook already has db owner-level write access, so it is reused here).
#
# Purview account: Purview-West2 (system-assigned managed identity,
# principalId ef32ae42-62e3-4302-b99a-d5b11e925e4a). Azure SQL AAD auth resolves this
# principal by its display name, which matches the Purview account name.

GRANT_PURVIEW_SQL_ACCESS = False
PURVIEW_MI_DISPLAY_NAME = "Purview-West2"

if not GRANT_PURVIEW_SQL_ACCESS:
    print("[SKIPPED] Set GRANT_PURVIEW_SQL_ACCESS = True and re-run this cell to grant access.")
elif DEMO_MODE:
    print("[DRY RUN] Skipping Purview MI grant.")
else:
    grant_cur = conn.cursor()
    grant_cur.execute(
        f"IF NOT EXISTS (SELECT 1 FROM sys.database_principals WHERE name = N'{PURVIEW_MI_DISPLAY_NAME}') "
        f"CREATE USER [{PURVIEW_MI_DISPLAY_NAME}] FROM EXTERNAL PROVIDER;"
    )
    grant_cur.execute(f"ALTER ROLE db_datareader ADD MEMBER [{PURVIEW_MI_DISPLAY_NAME}];")
    conn.commit()
    print(f"Granted db_datareader to [{PURVIEW_MI_DISPLAY_NAME}] on {DATABASE_NAME}.")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }
