import pandas as pd
# import matplotlib.pyplot as plt
import seaborn as sns
import pygwalker as pyg
import streamlit.components.v1 as components
import streamlit as st
import argparse

# ssh -L 8501:localhost:8501 dormeur


def main():
    # Set up argument parser
    parser = argparse.ArgumentParser(description="Visualize data through pygwalker and SSH port forwarding")
    parser.add_argument("input_file", help="The CSV file to visualize with pygwalker.")
    
    # Parse command line arguments
    args = parser.parse_args()

    # Adjust the width of the Streamlit page
    st.set_page_config(
        page_title="Use Pygwalker In Streamlit",
        layout="wide"
    )
    
    # Add Title
    st.title("Use Pygwalker In Streamlit")

    df = pd.read_csv(args.input_file)

    # Generate the HTML using Pygwalker
    pyg_html = pyg.to_html(df)
    
    # Embed the HTML into the Streamlit app
    components.html(pyg_html, height=1000, scrolling=True)

if __name__ == "__main__":
    main()

