import os
import re
from groq import Groq
from src.data_processor import DataProcessor
from src.embedder import Embedder

class RAGPipeline:
    def __init__(self, faiss_path, data_path):
        # Hardcode the Groq model name here
        self.model_name = "llama-3.1-8b-instant"  # or "llama-3.1-8b-instant" if that's your model
        self.faiss_path = faiss_path
        self.data_path = data_path

        # Load and preprocess data
        processor = DataProcessor(data_path=self.data_path, save_path=self.data_path)
        self.df = processor.load_data()
        processor.preprocess()
        self.df = processor.df

        # Medicine and brand names for detection
        self.generic_meds = self.df['Generic Name'].dropna().tolist()
        self.brand_names = self.df['Brand Name'].dropna().tolist()

        # Load embedding store
        self.embedder = Embedder()
        self.embedder.load_vector_store(faiss_load_path=self.faiss_path, data_df=self.df)

        # Initialize Groq API client
        self.client = Groq(api_key=os.getenv("GROQ_API_KEY"))

    def _extract_medicine_types(self, query):
        query_lower = query.lower()
        matched_generic = [med for med in self.generic_meds if re.search(r'\b' + re.escape(med.lower()) + r'\b', query_lower)]
        matched_brand = [brand for brand in self.brand_names if re.search(r'\b' + re.escape(brand.lower()) + r'\b', query_lower)]
        return matched_generic, matched_brand

    def run(self, user_query: str, context: str = None) -> str:
        greetings = ["hi", "hello", "hey", "good morning", "good evening"]
        user_query_clean = user_query.strip().lower()
        if user_query_clean in greetings:
            return "Hello! How can I help you with medicine information today?"

        # If context (PDF text) is provided
        if context is not None:
            # If the user asks for a summary or general info, use only PDF text
            summary_keywords = ["summarize", "summary", "report", "overview"]
            if any(kw in user_query.lower() for kw in summary_keywords):
                prompt = f"You are a helpful assistant. Use only the following context to answer the user's question. Be concise.\n\nContext:\n{context}\n\nUser's Question:\n{user_query}\n\nAnswer:"
                try:
                    result = self.client.chat.completions.create(
                        model=self.model_name,
                        messages=[{"role": "user", "content": prompt}],
                        temperature=0.7,
                        max_tokens=500,
                        top_p=0.9
                    )
                    return result.choices[0].message.content.strip()
                except Exception as e:
                    return f"Sorry, an error occurred during Groq API generation: {e}"
                # If the user asks what medicines are used in the PDF, extract from context
                medicine_keywords = ["medicine", "medicines", "drugs", "used in this pdf", "used in this report", "prescribed"]
                if any(kw in user_query.lower() for kw in medicine_keywords) and ("used" in user_query.lower() or "in this pdf" in user_query.lower() or "in this report" in user_query.lower()):
                    found_meds = []
                    for med in self.generic_meds + self.brand_names:
                        if med.lower() in context.lower():
                            found_meds.append(med)
                    if found_meds:
                        # Get details from database for found medicines
                        df_filtered = self.df[
                            (self.df['Generic Name'].isin(found_meds)) |
                            (self.df['Brand Name'].isin(found_meds))
                        ]
                        if not df_filtered.empty:
                            med_info = df_filtered.to_dict(orient='records')
                            # Compose a finished, meaningful summary
                            summary_lines = []
                            for info in med_info:
                                line = f"{info.get('Brand Name', info.get('Generic Name', ''))} (" \
                                       f"{info.get('Salt', '')}) - Contains {info.get('Generic Name', '')} " \
                                       f"({info.get('Strength', '')}) which is used to {info.get('Indication', '').lower()}."
                                summary_lines.append(line)
                            summary = " ".join(summary_lines)
                            advice = "However, please note that for any medical condition, always consult a qualified healthcare professional for diagnosis and treatment."
                            return f"Based on the PDF, the following medicines are prescribed: {summary} {advice}"
                        else:
                            return f"The following medicines were found in the PDF: {', '.join(found_meds)}. Please consult a healthcare professional for more details."
                    else:
                        return "No medicines were found in the PDF."
            # If the user asks about a medicine, cross-reference with database
            matched_generic, matched_brand = self._extract_medicine_types(user_query)
            found_meds = []
            for med in matched_generic + matched_brand:
                if med.lower() in context.lower():
                    found_meds.append(med)
            if found_meds:
                # Get details from database
                df_filtered = self.df[
                    (self.df['Generic Name'].isin(found_meds)) |
                    (self.df['Brand Name'].isin(found_meds))
                ]
                if not df_filtered.empty:
                    med_info = df_filtered.to_dict(orient='records')
                    med_details = '\n'.join([str(info) for info in med_info])
                    prompt = f"The following medicine(s) were found in the report and database.\n{med_details}\n\nUser's Question:\n{user_query}\n\nAnswer:"
                    try:
                        result = self.client.chat.completions.create(
                            model=self.model_name,
                            messages=[{"role": "user", "content": prompt}],
                            temperature=0.7,
                            max_tokens=500,
                            top_p=0.9
                        )
                        return result.choices[0].message.content.strip()
                    except Exception as e:
                        return f"Sorry, an error occurred during Groq API generation: {e}"
            # If no medicine found, fallback to PDF text only
            prompt = f"Use only the following context to answer the user's question.\n\nContext:\n{context}\n\nUser's Question:\n{user_query}\n\nAnswer:"
            try:
                result = self.client.chat.completions.create(
                    model=self.model_name,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.7,
                    max_tokens=500,
                    top_p=0.9
                )
                return result.choices[0].message.content.strip()
            except Exception as e:
                return f"Sorry, an error occurred during Groq API generation: {e}"

        symptom_keywords = [
            "i have", "my symptoms", "i feel", "i am suffering",
            "pain", "headache", "fever", "vomiting", "cough", "nausea"
        ]
        medical_advice_keywords = ['diagnose', 'symptoms', 'what should i take', 'sick']
        disclaimer = ""
        if any(symptom in user_query.lower() for symptom in symptom_keywords) or \
           any(keyword in user_query.lower() for keyword in medical_advice_keywords):
            disclaimer = (
                "Note: If your question pertains to symptoms or medical advice, "
                "please remember I am an AI assistant and not a healthcare professional. "
                "Always consult a qualified healthcare provider for diagnosis and treatment.\n\n"
            )

        price_keywords = ['price', 'cheapest', 'lowest price', 'least cost', 'cost effective']
        if any(pk in user_query.lower() for pk in price_keywords):
            matched_generic, matched_brand = self._extract_medicine_types(user_query)
            df_filtered = self.df[
                (self.df['Generic Name'].isin(matched_generic)) |
                (self.df['Brand Name'].isin(matched_brand))
            ] if (matched_generic or matched_brand) else self.df
            if df_filtered.empty:
                return "Sorry, no matching price information found."
            df_filtered = df_filtered.copy()
            df_filtered['Price'] = df_filtered['Price'].str.replace('₹', '', regex=False).astype(float)
            min_price = df_filtered['Price'].min()
            meds = df_filtered[df_filtered['Price'] == min_price]
            meds_list = ', '.join(
                set(meds['Generic Name'].fillna('')) |
                set(meds['Brand Name'].fillna('')))
            return f"The cheapest medicine(s) for your query: {meds_list} at ₹{min_price}"

        matched_generic, matched_brand = self._extract_medicine_types(user_query)
        intro_notes = ""
        if matched_generic or matched_brand:
            parts = []
            if matched_generic:
                parts.append(f"generic medicine(s): {', '.join(matched_generic)}")
            if matched_brand:
                parts.append(f"brand name(s): {', '.join(matched_brand)}")
            salts_info = []
            for brand in matched_brand:
                salts = self.df[self.df['Brand Name'] == brand]['Salt'].dropna().unique()
                if len(salts) > 0:
                    salts_info.append(f"Brand '{brand}' contains salt(s): {', '.join(salts)}")
                else:
                    salts_info.append(f"Brand '{brand}' has no salt information available.")
            intro_notes = f"Note: Query includes {', '.join(parts)}.\n" + "\n".join(salts_info) + "\n"

        # Use provided context if available, otherwise retrieve as before
        if context is not None:
            context_text = context
        else:
            retrieved_chunks = self.embedder.retrieve(user_query)
            if not retrieved_chunks:
                context_text = "No relevant information found in the database."
            else:
                max_length = 512
                chunked = []
                tok_count = 0
                for chunk in retrieved_chunks:
                    chunk_len = len(chunk.split())
                    if tok_count + chunk_len > max_length:
                        break
                    chunked.append(chunk)
                    tok_count += chunk_len
                context_text = "\n".join(chunked)

        prompt = f"""{disclaimer}{intro_notes}You are a helpful medical assistant.
Use only the following context to answer the user's question. Be concise. If information is missing, say so.

Context:
{context_text}

User's Question:
{user_query}

Answer:"""

        # Call Groq API
        try:
            result = self.client.chat.completions.create(
                model=self.model_name,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
                max_tokens=500,
                top_p=0.9
            )
            return result.choices[0].message.content.strip()
        except Exception as e:
            return f"Sorry, an error occurred during Groq API generation: {e}"
