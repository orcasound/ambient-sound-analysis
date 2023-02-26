import pandas as pd

# initialize list of lists
data = [['Cristiano Ronlado', 7], ['Juan Mata', 8], ['Bruno Fernandez', 18]]

# Create the pandas DataFrame
df = pd.DataFrame(data, columns=['Name', 'Jersey Number'])

print("-"*50)
print("Hello Everyone welcome to AWS BATCH")
print("-"*50)
print(df)
print("-"*50)