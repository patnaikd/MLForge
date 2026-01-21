"""Sample valid analysis code for testing."""

import pandas as pd

# Load data
df = pd.read_csv("data/sample.csv")

# Basic stats
print("Shape:", df.shape)
print("\nHead:")
print(df.head())
print("\nDescribe:")
print(df.describe())
