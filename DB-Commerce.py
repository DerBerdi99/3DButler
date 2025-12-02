import sqlite3

# Connect to the database
conn = sqlite3.connect('D:\\Programmtests\\FlaskEcom\\website\\db\\Commerce.db')
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

# Create table queries

queryUSERS = '''
CREATE TABLE "Users"( 
    "UserID" TEXT PRIMARY KEY,
    "AddressID" TEXT NOT NULL,
    "PaymentID" TEXT NOT NULL,
    "FirstName" TEXT NOT NULL,
    "LastName" TEXT NOT NULL,
    "Email" TEXT NOT NULL,
    "Phone" TEXT,
    "Gender" INTEGER,
    "Username" TEXT NOT NULL UNIQUE,
    "IsAdmin" INTEGER NOT NULL,
    "IsActive" INTEGER NOT NULL,
    FOREIGN KEY ("AddressID") REFERENCES Addresses("AddressID"),
    FOREIGN KEY ("PaymentID") REFERENCES Payment("PaymentID")
)'''


queryPASSWORDS = '''
    CREATE TABLE "Passwords" ( 
    "UserID" TEXT NOT NULL PRIMARY KEY UNIQUE, 
    "Password" TEXT NOT NULL
    )
'''

queryADMINNOTIFICATIONS = '''
CREATE TABLE "AdminNotifications" (
    "NotificationID" TEXT NOT NULL PRIMARY KEY,
    "ProjectID" TEXT NOT NULL,
    "AdminID" TEXT NOT NULL,
    "Timestamp" DATETIME NOT NULL,
    "Message" TEXT NOT NULL,
    "IsRead" INTEGER NOT NULL,
    FOREIGN KEY ("ProjectID") REFERENCES "Projects" ("ProjectID"),
    FOREIGN KEY ("AdminID") REFERENCES "Admins" ("AdminID")
)'''

queryADDRESSES = '''
    CREATE TABLE "Addresses" (
    "AddressID" TEXT NOT NULL,
    "UserID" TEXT NOT NULL,
    "Street" TEXT, 
    "City" TEXT,
    "Zipcode" TEXT,
    "Country" TEXT,
    "IsDefaultShipping" INTEGER,
    PRIMARY KEY("AddressID"),
    FOREIGN KEY ("UserID") REFERENCES "Users"("UserID") 
)'''
#cursor.execute('''DROP TABLE PAYMENTS''')
queryPAYMENTS = '''
CREATE TABLE "Payments"(
    "PaymentID" TEXT NOT NULL PRIMARY KEY,
    "UserID" TEXT NOT NULL,
    "Method" TEXT NOT NULL,
    "Token" TEXT,
    "LastIDDigits" TEXT,
    "Expiry" TEXT,
    "IsDefaultMethod" INTEGER,
    FOREIGN KEY ("UserID") REFERENCES "Users" ("UserID")
)
'''
#cursor.execute(queryPAYMENTS)
#cursor.execute('''DROP TABLE PRODUCTS''')
queryPRODUCTS = '''
CREATE TABLE "Products" (
    "ProductID" TEXT NOT NULL PRIMARY KEY,
    "UserID" TEXT NOT NULL,
    "ProductCategory" TEXT NOT NULL,
    "MaterialType" TEXT NOT NULL,
    "ProductName" TEXT NOT NULL,
    "ProductDescription" TEXT NOT NULL,
    "WeightG" REAL NOT NULL,
    "PrintTimeMin" INTEGER NOT NULL,
    "CreatedAt" TEXT NOT NULL,
    "StockQuantity" INTEGER NOT NULL,
    "IsActive" INTEGER NOT NULL,
    "ImagePath" TEXT,
    "IsShopReady" INTEGER NOT NULL DEFAULT 0,
    "Color" TEXT,
    "SourceProjectID" TEXT,
    FOREIGN KEY ("UserID") REFERENCES "Users" ("UserID"),
    FOREIGN KEY ("ProductCategory") REFERENCES "ProductCategories" ("CategoryName")
)'''

#cursor.execute("ALTER TABLE Products ADD COLUMN IsShopReady INTEGER NOT NULL DEFAULT 0;")
#cursor.execute(queryPRODUCTS)

queryPARTS = '''
    CREATE TABLE "Parts" (
    "PartID" TEXT PRIMARY KEY,
    "MaterialID" TEXT NOT NULL,
    "ProfileID" TEXT NOT NULL,
    "PartName" TEXT NOT NULL,
    "WeightG" REAL NOT NULL,
    "PrintTimeMin" INTEGER NOT NULL,
    "ManufacturingMethod" TEXT NOT NULL,
    "IsReusable" INTEGER NOT NULL,
    FOREIGN KEY ("MaterialID") REFERENCES "Materials" ("MaterialID"),
    FOREIGN KEY ("ProfileID") REFERENCES "PrintProfiles" ("ProfileID")
)'''

queryBILLOFMATERIALS = '''
CREATE TABLE "BillOfMaterials" (
    "ProductPartID" TEXT NOT NULL PRIMARY KEY,
    "ProductID" TEXT NOT NULL,
    "PartID" TEXT NOT NULL,
    "ProfileID" TEXT NOT NULL,
    FOREIGN KEY ("ProductID") REFERENCES "Products" ("ProductID"),
    FOREIGN KEY ("PartID") REFERENCES "Parts" ("PartID"),
    FOREIGN KEY ("ProfileID") REFERENCES "PrintProfiles" ("ProfileID")
)'''

cursor.execute('''DROP TABLE FILES''')
queryFILES = '''
    CREATE TABLE "Files" ( 
    "FileID" TEXT PRIMARY KEY, 
    "UserID" TEXT NOT NULL,
    "FilePath" TEXT NOT NULL,
    "FileName" TEXT NOT NULL,
    "FileSizeKB" INTEGER NOT NULL,
    FOREIGN KEY("UserID") REFERENCES "Users"("UserID")
)'''
cursor.execute(queryFILES)
cursor.execute('''DROP TABLE Orders''')

queryORDERS ='''
    CREATE TABLE "Orders" (
    "OrderID"           TEXT NOT NULL PRIMARY KEY,
    "UserID"            TEXT NOT NULL,
    "AddressID"         TEXT,
    "PaymentID"         TEXT,
    "SourceProjectID"   TEXT,
    
    "OrderStatus"       TEXT NOT NULL DEFAULT 'ORDER_CREATED', 
    "OrderDate"         TEXT NOT NULL,
    "OrderAmount"        INTEGER NOT NULL, 
    
    "PaymentStatus"     TEXT NOT NULL DEFAULT 'PENDING_PAYMENT', 
    "TransactionID"     TEXT, 
    "PaymentMethod"     TEXT,  

    FOREIGN KEY ("UserID") REFERENCES "Users" ("UserID"),
    FOREIGN KEY ("AddressID") REFERENCES "Addresses" ("AddressID"),
    FOREIGN KEY ("PaymentID") REFERENCES "Payments" ("PaymentID"),
    FOREIGN KEY ("SourceProjectID") REFERENCES "Projects" ("ProjectID")
)'''

cursor.execute(queryORDERS)

cursor.execute('''DROP TABLE ORDERPOSITIONS''')

queryORDERPOSITIONS = '''
CREATE TABLE "OrderPositions" (
    "PositionID" TEXT NOT NULL PRIMARY KEY,
    "OrderID" TEXT NOT NULL,
    "ProductID" TEXT NOT NULL,
    "ProductType" TEXT NOT NULL,
    "Quantity" INTEGER NOT NULL,
    "PricePerUnit" INTEGER NOT NULL,
    FOREIGN KEY ("OrderID") REFERENCES "Orders" ("OrderID"),
    FOREIGN KEY ("ProductID") REFERENCES "Products" ("ProductID")
)'''
cursor.execute(queryORDERPOSITIONS)
queryWISHLISTS='''
CREATE TABLE "WishLists" (
    "WishListID" TEXT NOT NULL PRIMARY KEY,
    "UserID" TEXT NOT NULL,
    "ProductID" TEXT NOT NULL,
    "DateAdded" DATETIME NOT NULL,
    FOREIGN KEY ("UserID") REFERENCES "Users" ("UserID"),
    FOREIGN KEY ("ProductID") REFERENCES "Products" ("ProductID")
)'''
#cursor.execute('''DROP TABLE PROJECTS''')
queryPROJECTS =  '''
    CREATE TABLE "Projects" (
    "ProjectID" TEXT PRIMARY KEY,
    "FileIDs" TEXT NOT NULL,
    "UserID" TEXT NOT NULL,
    "MaterialType" TEXT NOT NULL,
    "ProjectDescription" TEXT,
    "ProjectName" TEXT,
    "ProjectQuantity" INTEGER,
    "Status" TEXT,
    "VolumeCM3" REAL,
    "PrintTimeMin" INTEGER,
    "EstimatedMaterialG" INTEGER,
    "DateAdded" DATETIME,
    "Priority" INTEGER,
    "FinalQuotePrice" REAL,
    "QuoteDate" TEXT,
    FOREIGN KEY("FileIDs") REFERENCES "Files"("FileID"),
    FOREIGN KEY("UserID") REFERENCES "Users"("UserID")
)'''
#cursor.execute(queryPROJECTS)


queryPRODUCTPRICES = '''
CREATE TABLE IF NOT EXISTS "ProductPrices" (
    "PriceID" TEXT NOT NULL PRIMARY KEY,
    "ProductID" TEXT NOT NULL,
    "ProductPrice" INTEGER NOT NULL,
    "DateAdded" TEXT NOT NULL,
    FOREIGN KEY ("ProductID") REFERENCES "Products"("ProductID")
)
'''
querySHOPPINGCARTS_DEPRECATED = '''
CREATE TABLE IF NOT EXISTS "ShoppingCarts" (
    "CartItemID" INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
    "ProductID" TEXT NOT NULL,
    "DateAdded" TEXT NOT NULL,
    FOREIGN KEY ("ProductID") REFERENCES "Products" ("ProductID")
)
'''
queryVERIFICATIONTOKENS = '''
    CREATE TABLE "VerificationTokens" (
    "TokenID" TEXT PRIMARY KEY,
    "UserID" TEXT,
    "TokenHash" TEXT NOT NULL UNIQUE,
    "Expiry" DATETIME NOT NULL,
    "Created" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY("UserID") REFERENCES "Users"("UserID")

    )
'''
#try:
 #   cursor.execute("ALTER TABLE VerificationTokens ADD COLUMN TokenType TEXT NOT NULL DEFAULT 'UNKNOWN';")
#except sqlite3.OperationalError as e:
    # ignore if column already exists; re-raise other errors
 #   if 'duplicate column name' not in str(e).lower():
  #      raise

queryCOSTS = '''
    CREATE TABLE "Costs" (
    "CostID" TEXT PRIMARY KEY,
    "ProductID" TEXT NOT NULL,
    "TotalCost" INTEGER NOT NULL,
    "MaterialCost" INTEGER NOT NULL,
    "PrintTimeCost" INTEGER NOT NULL,
    FOREIGN KEY("ProductID") REFERENCES "Products"("ProductID")
)'''
#cursor.execute('''DROP TABLE PRINTERS''')
queryPRINTERS='''
    CREATE TABLE "Printers" (
    "PrinterID" TEXT PRIMARY KEY,
    "HotendID" TEXT NOT NULL,
    "PrintHeadID" TEXT NOT NULL,
    "BuildPlateID" TEXT NOT NULL,
    "PrinterName" TEXT NOT NULL,
    "Status" TEXT NOT NULL,
    "RuntimeHours" INTEGER NOT NULL,
    FOREIGN KEY("HotendID") REFERENCES "SpareParts"("HotendID"),
    FOREIGN KEY("PrintHeadID") REFERENCES "SpareParts"("PrintHeadID"),
    FOREIGN KEY("BuildPlateID") REFERENCES "SpareParts"("BuildPlateID") 
)'''
#cursor.execute(queryPRINTERS)

querySPAREPARTS='''
    CREATE TABLE "SpareParts" (
    "PartID" TEXT PRIMARY KEY,
    "HotendID" TEXT,
    "PrintHeadID" TEXT,
    "BuildPlateID" TEXT
)'''


spare_parts = [
    ('SPAR_001', 'HOTEND_V6', 'PH_04', 'BP_220x220'),
    ('SPAR_002', 'HOTEND_V6', 'PH_06', 'BP_300x300'),
    ('SPAR_003', 'HOTEND_PRO', 'PH_04', 'BP_250x210'),
]
'''cursor.executemany(
    'INSERT OR IGNORE INTO SpareParts (PartID, HotendID, PrintHeadID, BuildPlateID) VALUES (?, ?, ?, ?)',
    spare_parts
)'''

# insert three printers that reference the spare part component IDs above
printers = [
    ('PRN_001', 'HOTEND_V6', 'PH_04', 'BP_220x220', 'AlphaPrinter', 'online', 1200, 5),   # cost per min in cents
    ('PRN_002', 'HOTEND_V6', 'PH_06', 'BP_300x300', 'BetaPrinter', 'maintenance', 800, 7),
    ('PRN_003', 'HOTEND_PRO', 'PH_04', 'BP_250x210', 'GammaPrinter', 'idle', 400, 6),
]
'''cursor.executemany(
    'INSERT OR IGNORE INTO Printers (PrinterID, HotendID, PrintHeadID, BuildPlateID, PrinterName, Status, RuntimeHours, CostPerMin) VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
    printers
)'''

#cursor.execute('''DROP TABLE PrintProfiles''')
queryPRINTPROFILES = '''
    CREATE TABLE "PrintProfiles" (
    "ProfileID" TEXT PRIMARY KEY,
    "ProfileName" TEXT NOT NULL,
    "SpeedMultiplier" REAL,
    "MarkupMultiplier" REAL,
    "InfillDensity" INTEGER,
    "LayerHeightMM" REAL,
    "CostMultiplier" REAL,
    "CostPerMin" REAL
)'''
#cursor.execute(queryPRINTPROFILES)

print_profiles = [
    ('PROF_PLA50S', 'PLA50Slow', 0.5, 1.1, 15, 0.2, 0.9, 0.02),
    ('PROF_PLA100S', 'PLA100Slow', 1.0, 1.05, 20, 0.15, 1.0, 0.04),
    ('PROF_PLA50F', 'PLA50Fast', 0.5, 1.3, 10, 0.3, 0.7, 0.01),
    ('PROF_PLA100F', 'PLA100Fast', 1.0, 1.25, 15, 0.2, 0.85, 0.02),
    ('PROF_ABS50S', 'ABS50Slow', 0.5, 1.15, 18, 0.2, 1.1, 0.03),
    ('PROF_ABS100S', 'ABS100Slow', 1.0, 1.1, 22, 0.15, 1.15, 0.06),
    ('PROF_ABS50F', 'ABS50Fast', 0.5, 1.35, 12, 0.3, 0.9, 0.02),
    ('PROF_ABS100F', 'ABS100Fast', 1.0, 1.3, 16, 0.2, 1.0, 0.04)
]
'''cursor.executemany(
    'INSERT OR IGNORE INTO PrintProfiles (ProfileID, ProfileName, SpeedMultiplier, MarkupMultiplier, InfillDensity, LayerHeightMM, CostMultiplier, CostPerMin) VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
    print_profiles
)'''

queryMATERIALS ='''
    CREATE TABLE "Materials" (
    "MaterialID" TEXT PRIMARY KEY,
    "MaterialName" TEXT NOT NULL,
    "Color" TEXT,
    "DensityGCM3" REAL,
    "CostPerKG" INTEGER,
    "InStockKG" INTEGER
    )
'''
materials = [
    ('MAT_ABS', 'ABS', 'Natural', 1.04, 25, 100),   # density g/cm3, cost per kg (est.), in-stock kg (est.)
    ('MAT_PLA', 'PLA', 'Natural', 1.24, 20, 150)
]
'''cursor.executemany(
    'INSERT OR IGNORE INTO Materials (MaterialID, MaterialName, Color, DensityGCM3, CostPerKG, InStockKG) VALUES (?, ?, ?, ?, ?, ?)',
    materials
)'''



#cursor.execute('''DROP TABLE ProductCategories''')
queryCATEGORIES = '''
CREATE TABLE "ProductCategories" (
    "CategoryID" TEXT PRIMARY KEY,
    "CategoryName" TEXT NOT NULL UNIQUE
)'''
#cursor.execute(queryCATEGORIES)
categories = [
    ('CAT_001', 'Electronics'),
    ('CAT_002', 'Furniture'),
    ('CAT_003', 'Clothing'),
    ('CAT_004', 'Books'),
    ('CAT_005', 'Home & Garden')
]
#cursor.executemany('INSERT INTO ProductCategories (CategoryID, CategoryName) VALUES (?, ?)', categories)

#cursor.execute('''DROP TABLE ProjectMessages''')
queryPROJECTMESSAGES = '''CREATE TABLE "ProjectMessages" ( 
    "CommID" TEXT PRIMARY KEY, 
    "ProjectID" TEXT NOT NULL, 
    "SenderType" TEXT NOT NULL, 
    "MessageText" TEXT NOT NULL, 
    "Timestamp" TEXT NOT NULL, 
    "IsUnreadAdmin" INTEGER NOT NULL DEFAULT 1, 
    "RequiresFileUpload" INTEGER DEFAULT 0,
    FOREIGN KEY("ProjectID") REFERENCES "Projects"("ProjectID") ON DELETE CASCADE 
)
'''

#query=('''ALTER TABLE ProjectMessages ADD COLUMN RequiredFilesProvided INTEGER DEFAULT 0;''')
#cursor.execute(queryPROJECTMESSAGES)
#cursor.execute(query)
#-- 1. Tabelle für den Warenkorb-Header (Container pro Benutzer)
#-- Ein Benutzer hat EINEN aktiven Warenkorb.
querySHOPPINGCARTS= '''CREATE TABLE "ShoppingCarts" (
    "CartID" INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
    "UserID" TEXT NOT NULL UNIQUE, 
    "DateCreated" TEXT NOT NULL,
    FOREIGN KEY ("UserID") REFERENCES "Users" ("UserID")
);'''



#-- 2. Tabelle für die Positionen im Warenkorb (die tatsächlichen Produkte mit Mengen)
#-- Jede Zeile ist ein Produkt mit einer Menge, verknüpft mit dem Warenkorb des Benutzers.
queryCARTPOSITIONS = '''CREATE TABLE "CartPositions" (
    "PositionID" INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
    "CartID" INTEGER NOT NULL,
    "ProductID" TEXT NOT NULL,
    "Quantity" INTEGER NOT NULL, 
    "DateAdded" TEXT NOT NULL,
    
    FOREIGN KEY ("CartID") REFERENCES "ShoppingCarts" ("CartID"),
    FOREIGN KEY ("ProductID") REFERENCES "Products" ("ProductID"),
    
    UNIQUE ("CartID", "ProductID") 
);
'''
#cursor.execute(queryPROJECTMESSAGES)
#cursor.execute('''DROP TABLE SHOPPINGCARTS''')

#cursor.execute(querySHOPPINGCARTS)
#cursor.execute(queryCARTPOSITIONS)



queryCONFIGURATIONS = '''
CREATE TABLE "Configurations" (
    "Key" TEXT PRIMARY KEY,       
    "Value" INTEGER NOT NULL      
)'''


#cursor.execute('''DELETE FROM Configurations''')
#cursor.execute('''INSERT INTO Configurations (Key, Value) VALUES ('MaxProjects', 4)''')
#cursor.execute('''INSERT INTO Configurations (Key, Value) VALUES ('UnderReview', 3)''')

#cursor.execute(queryPROJECTMESSAGES)
#cursor.execute(queryCONFIGURATIONS)

#cursor.execute('''DELETE FROM Orders''')
#cursor.execute('''DELETE FROM OrderDetails''')
#cursor.execute('''DELETE FROM Passwords''')
#cursor.execute('''DELETE FROM ShoppingCart''')
#cursor.execute('''DELETE FROM WishList''')

#cursor.execute('''DROP TABLE Files''')
#cursor.execute('''DROP TABLE Users''')
#cursor.execute('''DROP TABLE Payments''')
#cursor.execute('''DROP TABLE Addresses''')
#cursor.execute('''DROP TABLE Passwords''')
#cursor.execute('''DROP TABLE Projects''')
#cursor.execute('''DROP TABLE Orders''')
#cursor.execute('''DROP TABLE OrderDetails''')
#cursor.execute('''DROP TABLE PrintProfiles''')
#cursor.execute('''DROP TABLE ProductPrice''')
#cursor.execute('''DROP TABLE Products''')
#cursor.execute('''DROP TABLE ShoppingCart''')
#cursor.execute('''DROP TABLE WishList''')
#cursor.execute('''DROP TABLE VerificationTokens''')
#cursor.execute('''DROP TABLE Materials''')

#cursor.execute(queryUSERS)
#cursor.execute(queryADMINS) 
#cursor.execute(queryPASSWORDS)  
#cursor.execute(queryADMINNOTIFICATIONS) 
#cursor.execute(queryADDRESSES)
#cursor.execute(queryPAYMENTS)   
#cursor.execute(queryPRODUCTS)
#cursor.execute(queryPARTS)
#cursor.execute(queryBILLOFMATERIALS)
#cursor.execute(queryPRINTPROFILES)
#cursor.execute(queryFILES)
#cursor.execute(queryORDERS)
#cursor.execute(queryORDERPOSITIONS)
#cursor.execute(queryWISHLISTS)
#cursor.execute(queryPRODUCTPRICES)
#cursor.execute(querySHOPPINGCARTS)
#cursor.execute(queryCOSTS)
#cursor.execute(queryPRINTERS)
#cursor.execute(querySPAREPARTS) 
#cursor.execute(queryPROJECTS)
#cursor.execute(queryMATERIALS)
#cursor.execute(queryVERIFICATIONTOKENS)
#cursor.execute(queryCATEGORIES)


#cursor.execute('''ALTER TABLE ProjectMessages ADD COLUMN QuotePrice REAL;''')
#cursor.execute('''ALTER TABLE ProjectMessages ADD COLUMN IsQuote INTEGER DEFAULT 0;''')
#cursor.execute('''ALTER TABLE Projects ADD COLUMN FinalQuotePrice REAL;''')

#cursor.execute('''ALTER TABLE Projects ADD COLUMN QuoteDate TEXT;''')

#cursor.execute('''ALTER TABLE Orders ADD COLUMN PaymentMethod TEXT;''')

#cursor.execute('''ALTER TABLE Products ADD COLUMN SourceProjectID TEXT;''')
#cursor.execute('''DELETE FROM Files WHERE FileID = 'FILE_7c044b0d-e2c8-4dfe-94a1-cb61b7990a51';''')
#cursor.execute('''DELETE FROM Projects WHERE ProjectID = 'PROJ_c12f860a-d310-4c6e-a0cd-aa08ff4c7185';''')

#project_id_to_check = '6815c890-d72b-491a-98cf-d6a7537f2907' # Beispiel-ID
#query = "SELECT ProductID FROM Products WHERE ProductID = ?"



"""
# Führen Sie die Abfrage mit Parametern aus
cursor.execute(query, (project_id_to_check,))

# 3. Ergebnis abrufen
# fetchone() gibt entweder einen Tupel (z.B. ('Propellerhut-ID',)) oder None zurück
result = cursor.fetchone() 

# 4. Ergebnis auswerten und printen
if result:
    # Das Ergebnis ist ein Tupel, also nehmen wir das erste Element [0]
    product_id = result[0]
    print(f"✅ Produkt gefunden! ProductID: {product_id}")
else:
    print(f"❌ KEIN Produkt gefunden für ProductID: {project_id_to_check}")

conn.commit()
cursor.close()
conn.close()

# Execute table creation queries

cursor.execute(querySHOPPINGCART)
cursor.execute(queryPRODUCTS)
cursor.execute(queryPRODUCTPRICE)
cursor.execute(queryORDERS)

# Insert data into Products table
products = [
    ('P004', 'Quadratpflaster BERTGOLD', 'Description for Product B', 10, '2025-02-04'),
    ('P005', 'Quadratpflaster PATRIOT', 'Description for Product A', 20, '2025-02-04'),
    ('P006', 'Quadratpflaster LAVENDER', 'Description for Product C', 15, '2025-02-04')
]

cursor.executemany('INSERT INTO Products (ProductID, ProductName, ProductDescription, StockQuantity, Created) VALUES (?, ?, ?, ?, ?)', products)

# Insert data into ProductPrice table
product_prices = [
    ('PR004', 'P004', 1999),
    ('PR005', 'P005', 2999),
    ('PR006', 'P006', 1999)
]
cursor.executemany('INSERT INTO ProductPrice (PriceID, ProductID, Price) VALUES (?, ?, ?)', product_prices)

# Commit the changes
conn.commit()

# Query to fetch data
query = '''
SELECT Products.ProductID, Products.StockQuantity, Products.ProductName, ProductPrice.Price, Products.ProductDescription
FROM Products
JOIN ProductPrice ON Products.ProductID = ProductPrice.ProductID
'''

cursor.execute(query)
data = cursor.fetchall()

# Convert rows to dictionaries for readable output
column_names = [description[0] for description in cursor.description]
results = [dict(zip(column_names, row)) for row in data]

# Print the fetched data
print(results)

# Close the connection
cursor.close()
conn.close()
"""
#cursor.execute('''DROP TABLE Payment''')
conn.commit()
cursor.close()
conn.close()