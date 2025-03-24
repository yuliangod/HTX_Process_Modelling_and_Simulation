import random
from collections import Counter

import numpy as np
import pandas as pd
import plotly.express as px
import simpy
import streamlit as st

from analysis import Analysis
from simulation import EmergencyDepartment, Station

st.set_page_config(layout="wide")  # Expands the page width

# Define available distributions
DISTRIBUTION_OPTIONS = {
    "Exponential": lambda rate: lambda: np.random.exponential(1 / rate),
    "Normal": lambda mu_sigma: lambda: np.random.normal(mu_sigma[0], mu_sigma[1]),
    "Uniform": lambda low_high: lambda: np.random.uniform(low_high[0], low_high[1])
}

# Initialize session state for storing station configurations if not already present
if "stations" not in st.session_state:
    st.session_state.stations = {
        "Main Lab": [
            {"name": "Main Lab 1", "num_staff": 1, "distribution": "Exponential", "parameters": {"rate": 1/5}, "prob_station_needed": 1},
            {"name": "Main Lab 2", "num_staff": 1, "distribution": "Exponential", "parameters": {"rate": 1/5}, "prob_station_needed": 0.5},
            {"name": "Main Lab 3", "num_staff": 1, "distribution": "Exponential", "parameters": {"rate": 1/5}, "prob_station_needed": 0.5},
            {"name": "Main Lab 4", "num_staff": 1, "distribution": "Exponential", "parameters": {"rate": 1/5}, "prob_station_needed": 0.5}
        ],
        "Fast Track Lab": [
            {"name": "Fast Track Lab 1", "num_staff": 1, "distribution": "Exponential", "parameters": {"rate": 1/5}, "prob_station_needed": 1},
        ],
        "Main Doctor's Room": [
            {"name": "Main Doctor's Room", "num_staff": 1, "distribution": "Exponential", "parameters": {"rate": 1/5}, "prob_station_needed": 1}
        ],
        "Fast Track Doctor's Room": [
            {"name": "Fast Track Doctor's Room", "num_staff": 1, "distribution": "Exponential", "parameters": {"rate": 1/5}, "prob_station_needed": 1}
        ],
        "Main Beds": [
            {"name": "Main Beds", "num_staff": 30, "distribution": "Exponential", "parameters": {"rate": 1/720}, "prob_station_needed": 0.01}
        ]
    }
    
if "patient" not in st.session_state:
    st.session_state.patient = {
        "Patient" : {"distribution":"Exponential", "parameters":{"rate":1/5}, "prob_patient_fast_track":0.8}
    }

def check_duplicate_names(station_type="Main Lab"):
    # Extract all existing station names
    existing_names = [lab["name"] for lab in st.session_state.stations[station_type]]
    #print("EXISTING", existing_names)
    
    duplicates = [item for item, count in Counter(existing_names).items() if count > 1]

    # Optional: Show a warning message if it's a duplicate
    if len(duplicates) > 0:
        st.warning(f"Duplicate name detected: {duplicates}. Please use a unique name.")

st.title("Emergency Department Simulation")

# Function to update distribution fields dynamically based on selected distribution
def update_distribution_fields(dist_param_container, selected_dist, dist_params, idx, station_config, station_type="Main"):
    with dist_param_container:
        station_config["parameters"] = {}
        if selected_dist == "Exponential":
            station_config["parameters"]["rate"] = st.number_input("Rate (λ)", value=dist_params.get("rate", 1.0), key=f"{station_type} Lab {idx} Expo Mean", format="%.5f")
        elif selected_dist == "Normal":
            cols = st.columns(2)
            station_config["parameters"]["mean"] = cols[0].number_input("Mean (μ)", value=dist_params.get("mean", 5.0), key=f"{station_type} Lab {idx} Norm Mean")
            station_config["parameters"]["std"] = cols[1].number_input("Standard Deviation (σ)", value=dist_params.get("std", 1.0), key=f"{station_type} Lab {idx} Norm Std")
        elif selected_dist == "Uniform":
            cols = st.columns(2)
            station_config["parameters"]["low"] = cols[0].number_input("Lower Bound", value=dist_params.get("low", 1.0), key=f"{station_type} Lab {idx} Uni Low")
            station_config["parameters"]["high"] = cols[1].number_input("Upper Bound", value=dist_params.get("high", 10.0), key=f"{station_type} Lab {idx} Uni High")

def station_settings(station_type="Main Lab"):
    emoji = ""
    if "Lab" in station_type:
        emoji = "🧪"  # Lab emoji
    elif "Doctor" in station_type:
        emoji = "👨‍⚕️"  # Doctor emoji
    elif "Bed" in station_type:
        emoji = "🛏️"  # Bed emoji
        
    # Collapsible container for Main Labs
    with st.expander(f"{emoji} **{station_type} Configuration**", expanded=True):
        # Loop through the list of Main Labs and display them
        for idx, station_config in enumerate(st.session_state.stations[f"{station_type}"]):
            # Create a container for the row
            with st.container():
                # Create columns for inputs in the row
                cols = st.columns([2, 1.2, 2, 4, 2, 2])  # Adjusted column sizes for the layout
                
                # Station configuration form inside the container
                with st.form(f"{station_type.lower()}_form_{idx}", clear_on_submit=True):
                    # Station Name input
                    station_config['name'] = cols[0].text_input("Name", value=station_config['name'], key=f"{station_type}_name_{idx}")
                    # Number of Staff input
                    if "Bed" in station_type:
                        num_staff_input_name = "Beds"
                    elif "Doctor" in station_type:
                        num_staff_input_name = "Doctors"
                    elif "Lab" in station_type:
                        num_staff_input_name = "Nurses"
                        
                    station_config['num_staff'] = cols[1].number_input(num_staff_input_name, value=station_config['num_staff'], key=f"{station_type}_num_staff_{idx}")
                    # Distribution selection
                    selected_dist = cols[2].selectbox("Treatment Time Dist", DISTRIBUTION_OPTIONS.keys(), index=list(DISTRIBUTION_OPTIONS.keys()).index(station_config['distribution']), key=f"{station_type}_dist_select_{idx}")
                    station_config["distribution"] = selected_dist
                    # Only update station_config if there's a change
                    if selected_dist != st.session_state[f"{station_type}_dist_select_{idx}"]:
                        st.rerun()  # Force Streamlit to rerun to reflect immediate change
                    #station_config["distribution"] = selected_dist
                    
                    # Parameter settings next to the distribution dropdown
                    dist_params_container = cols[3].container()  # Column for distribution params
                    update_distribution_fields(dist_params_container, selected_dist, station_config['parameters'], idx=idx, station_config=station_config, station_type=station_type)
                    
                    # Probability of station needed
                    if "Bed" in station_type:
                        prob_disabled = False # Disable input if it's the first Lab
                    else:
                        prob_disabled = (idx == 0)
                    station_config['prob_station_needed'] = cols[4].number_input("Prob Needed", value=station_config['prob_station_needed'], key=f"{station_type}_prob_station_needed_{idx}", disabled=prob_disabled)
                
                # Remove button in the same row as the station configuration
                remove_button = cols[5].button(f"Remove", key=f"{station_type}_remove_{idx}", disabled=(idx == 0))
                if remove_button:
                    st.session_state.stations[f"{station_type}"].pop(idx)
                    st.success(f"Removed {station_config['name']}.")
                    st.rerun()

        # Add New Lab Button within the collapsible container
        if "Lab" in station_type:
            if st.button(f"➕ Add New {station_type}", key=f"{station_type}_add_new_button"):
                # Add a new lab configuration to the session state
                new_station_config = {
                    "name": f"{station_type} {len(st.session_state.stations[station_type]) + 1}",
                    "num_staff": 1,
                    "distribution": "Exponential",
                    "parameters": {"rate": 1/5},
                    "prob_station_needed": 1
                }
                st.session_state.stations[station_type].append(new_station_config)
                st.success(f"Added new {station_type} row.")
                st.rerun()
            
        check_duplicate_names(station_type=station_type)

def patient_settings():
    # Collapsible container for Main Labs
    with st.expander(f"**😷Patients Configuration**", expanded=True):
        # Create a container for the row
        with st.container():
            # Create columns for inputs in the row
            cols = st.columns([2, 1.2, 2, 4, 2, 2])  # Adjusted column sizes for the layout
            
            station_config = st.session_state.patient["Patient"]
            # Station configuration form inside the container
            with st.form(f"patient_form", clear_on_submit=True):
                station_config['prob_patient_fast_track'] = cols[1].number_input("Probability Patient is Fast Track", value=station_config['prob_patient_fast_track'], key=f"prob_patient_fast_track")

                # Distribution selection
                selected_dist = cols[2].selectbox("Treatment Time Dist", DISTRIBUTION_OPTIONS.keys(), index=list(DISTRIBUTION_OPTIONS.keys()).index(station_config['distribution']), key=f"patient_dist_select")
                station_config["distribution"] = selected_dist
                # Only update station_config if there's a change
                if selected_dist != st.session_state[f"patient_dist_select"]:
                    st.rerun()  # Force Streamlit to rerun to reflect immediate change
                #station_config["distribution"] = selected_dist
                
                # Parameter settings next to the distribution dropdown
                dist_params_container = cols[3].container()  # Column for distribution params
                update_distribution_fields(dist_params_container, selected_dist, station_config['parameters'], idx=0, station_config=station_config, station_type="patient")
                
station_settings(station_type="Main Lab")
station_settings(station_type="Main Doctor's Room")
station_settings(station_type="Main Beds")
station_settings(station_type="Fast Track Lab")
station_settings(station_type="Fast Track Doctor's Room")
patient_settings()

def get_distribution_function(distribution_name, parameters):
    """ Returns a callable function that generates random values from the chosen distribution. """
    if distribution_name == "Exponential":
        rate = parameters["rate"]
        return lambda: np.random.exponential(1 / rate)
    elif distribution_name == "Normal":
        mean, std = parameters["mean"], parameters["std"]
        return lambda: np.random.normal(mean, std)
    elif distribution_name == "Uniform":
        low, high = parameters["low"], parameters["high"]
        return lambda: np.random.uniform(low, high)
        
#st.write(st.session_state)

def get_stations_list(station_type="Main Lab"):
    # Convert session state labs to Station objects
    stations_list = [
        Station(
            name=station_config['name'],
            num_staff=station_config['num_staff'],
            treatment_time_dist=get_distribution_function(station_config['distribution'], station_config['parameters']),
            prob_station_needed=station_config['prob_station_needed']
        )
        for station_config in st.session_state.stations[station_type]
    ]
    
    return stations_list

st.write("Check For Initialisation Bias in this Section")
with st.container():
    cols = st.columns(4)
    # Run simulation button outside the container
    until = cols[1].number_input("Simulation Duration", value=12000)
    mavg_value_1 = cols[2].number_input("1st Moving Average Window", value=10)
    mavg_value_2 = cols[3].number_input("2nd Moving Average Window", value=30)
    with cols[0]:
        st.write(" ")
        check_ini_bias_btn = st.button("Check Initialisation Bias")

    if check_ini_bias_btn:
        env = simpy.Environment()

        main_labs_list = get_stations_list(station_type="Main Lab")
        main_dr_room = get_stations_list(station_type="Main Doctor's Room")[0]
        main_bed = get_stations_list(station_type="Main Beds")[0]
        
        ft_labs_list = get_stations_list(station_type="Fast Track Lab")
        ft_dr_room = get_stations_list(station_type="Fast Track Doctor's Room")[0]
        
        prob_patient_fast_track=st.session_state.patient["Patient"]["prob_patient_fast_track"]
        patient_interarrival_dist=get_distribution_function(st.session_state.patient["Patient"]['distribution'], st.session_state.patient["Patient"]['parameters'])

            
        # Create a new simulation environment
        ED = EmergencyDepartment(env, main_labs=main_labs_list, main_dr_room=main_dr_room, main_bed=main_bed, ft_labs=ft_labs_list, ft_dr_room=ft_dr_room, prob_patient_fast_track=prob_patient_fast_track, patient_interarrival_dist=patient_interarrival_dist)
        # Run the simulation
        ED.run(until=until)

        A = Analysis()
        queue_df, busy_df = A.get_df(ED)
        
        # Streamlit app content for the ED page
        st.subheader("📊 Emergency Department Simulation Results")

        # Display a message explaining the simulation
        st.write(
            "This page displays the queue length over time for various stations in the Emergency Department. "
            "You can use this visualization to track the workload at each station during the simulation."
        )
        
        num_iterations = 5
        
        queue_df_list, busy_df_list, queue_bin_df_list, busy_bin_df_list, queue_mavg, busy_mavg = A.run_batch(num_iterations=num_iterations, batch_run_size=until, main_labs=main_labs_list, main_dr_room=main_dr_room, main_bed=main_bed, ft_labs=ft_labs_list, ft_dr_room=ft_dr_room, mavg_list=[mavg_value_1, mavg_value_2], prob_patient_fast_track=prob_patient_fast_track, patient_interarrival_dist=patient_interarrival_dist)
        
        st.write("Queue Length Welch's Test")
        tab_names = [col for col in queue_mavg.columns if col not in {"Time", "Station"}]

        # Create separate tabs first
        tabs = st.tabs(tab_names)

        # Assign each plot to its respective tab
        for i, tab in enumerate(tabs):
            with tab:  # Ensure each plot is inside the correct tab
                fig_queue_mavg = px.line(queue_mavg, x='Time', y=tab_names[i], color='Station', 
                                    title=f"Queue Length at Each Station{tab_names[i]} Over Time", 
                                    line_shape='hv')
                st.plotly_chart(fig_queue_mavg, key=f"queue_mavg_{i}")
                
                fig_busy_mavg = px.line(busy_mavg, x='Time', y=tab_names[i], color='Station', 
                                    title=f"Busy Staff at Each Station {tab_names[i]} Over Time",
                                    line_shape='hv')
                st.plotly_chart(fig_busy_mavg, key=f"busy_mavg_{i}")
                
        with st.expander("Individual simulations"):
            tab_names = ["Simulation " + str(i) for i in range(1,num_iterations+1)]
            for i,tab in enumerate(st.tabs(tab_names)):
                with tab:
                    # Plotting the queue length data using Plotly
                    st.write("Queue Length at Each Station Over Time")
                    st.line_chart(queue_df_list[i], x='Time', y='Queue Length', color='Station')

                    # Plotting the busy staff data using Plotly
                    st.write("Number of Busy Staff at Each Station Over Time")
                    st.line_chart(busy_df_list[i], x='Time', y='Busy Staff', color='Station')
                
st.write("Get simulation results here")
with st.container():
    cols = st.columns(4)
    burn_in_period = cols[1].number_input("Burn in Period", value=3200)
    num_iterations = cols[2].number_input("Num Iterations", value=20)
    confidence_level = cols[3].number_input("Confidence Interval", value=0.95)
    with cols[0]:
        st.write(" ")
        st.write(" ")
        results_btn = st.button("Get Simulation Results")
    if results_btn:
        env = simpy.Environment()

        main_labs_list = get_stations_list(station_type="Main Lab")
        main_dr_room = get_stations_list(station_type="Main Doctor's Room")[0]
        main_bed = get_stations_list(station_type="Main Beds")[0]
        
        ft_labs_list = get_stations_list(station_type="Fast Track Lab")
        ft_dr_room = get_stations_list(station_type="Fast Track Doctor's Room")[0]
        
        prob_patient_fast_track=st.session_state.patient["Patient"]["prob_patient_fast_track"]
        patient_interarrival_dist=get_distribution_function(st.session_state.patient["Patient"]['distribution'], st.session_state.patient["Patient"]['parameters'])
        
        A = Analysis()
        queue_results_df, busy_staff_results_df = A.run_analysis_stat(burn_in_period=burn_in_period, confidence_level=confidence_level, num_iterations=num_iterations, main_labs=main_labs_list, main_dr_room=main_dr_room, main_bed=main_bed, ft_labs=ft_labs_list, ft_dr_room=ft_dr_room, prob_patient_fast_track=prob_patient_fast_track, patient_interarrival_dist=patient_interarrival_dist)
        
        st.dataframe(queue_results_df)
        st.dataframe(busy_staff_results_df)