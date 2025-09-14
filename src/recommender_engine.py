import pandas as pd

class RecommenderEngine:
    """
    A class to find generic drug alternatives based on active pharmaceutical ingredients.
    This functionality is integrated into the RAG pipeline in the final version.
    """
    def __init__(self, data_df):
        self.df = data_df

    def find_alternatives(self, drug_name):
        """
        Finds equivalent drugs based on a given brand name's composition.
        
        Args:
            drug_name (str): The name of the drug to find alternatives for.
        
        Returns:
            tuple: A tuple containing a DataFrame of alternatives and a status message.
        """
        # Find the row for the requested drug
        drug_row = self.df[self.df['Brand Name'].str.contains(drug_name, case=False, na=False)]
        
        if drug_row.empty:
            return None, "Drug not found in database."

        # Get the composition (Salt) of the drug
        composition = drug_row['Salt'].iloc[0]

        # Find all other drugs with the same composition
        alternatives = self.df[
            (self.df['Salt'].str.contains(composition, case=False, na=False)) &
            (self.df['Brand Name'].str.lower() != drug_name.lower())
        ]
        
        if alternatives.empty:
            return None, "No generic alternatives found for this drug."

        return alternatives, "Alternatives found."
