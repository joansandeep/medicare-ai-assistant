import pandas as pd
import os

class DataProcessor:
    def __init__(self, data_path, save_path):
        self.data_path = data_path
        self.save_path = save_path
        self.df = None

    def load_data(self):
        try:
            self.df = pd.read_csv(self.data_path)
            print("Dataset loaded successfully!")
        except FileNotFoundError:
            raise FileNotFoundError("CSV file not found. Please check the path.")
        return self.df

    def preprocess(self):
        if self.df is None:
            self.load_data()

        # Handle missing values
        self.df = self.df.fillna('')

        # Create a single 'text' column for embedding. This combines all relevant information.
        # Updated to use the correct column names provided by you.
        self.df['text'] = self.df.apply(lambda row: 
            f"Generic Name: {row['Generic Name']}. "
            f"Brand Name: {row['Brand Name']}. "
            f"Composition (Salt): {row['Salt']}. "
            f"Manufacturer: {row['Manufacturer']}. "
            f"Uses: {row['Uses']}. "
            f"Side Effects: {row['Side Effects']}. "
            f"Price: {row['Price']}.", axis=1
        )
        print("Data preprocessed and 'text' column created.")

    def save_processed_data(self):
        if self.df is None:
            self.preprocess()
        
        # Ensure the directory exists
        os.makedirs(os.path.dirname(self.save_path), exist_ok=True)
        self.df.to_csv(self.save_path, index=False)
        print(f"Processed data saved to {self.save_path}")
        return self.df
