import random
from collections import Counter

import numpy as np
import pandas as pd
import plotly.express as px
import simpy
import streamlit as st

from ED import EmergencyDepartment, Station

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
            
station_settings(station_type="Main Lab")
station_settings(station_type="Main Doctor's Room")
station_settings(station_type="Main Beds")
station_settings(station_type="Fast Track Lab")
station_settings(station_type="Fast Track Doctor's Room")

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

def get_stations_list(env, station_type="Main Lab"):
    # Convert session state labs to Station objects
    stations_list = [
        Station(
            env=env,
            name=station_config['name'],
            num_staff=station_config['num_staff'],
            treatment_time_dist=get_distribution_function(station_config['distribution'], station_config['parameters']),
            prob_station_needed=station_config['prob_station_needed']
        )
        for station_config in st.session_state.stations[station_type]
    ]
    
    return stations_list

# Run simulation button outside the container
if st.button("Run simulation"):
    env = simpy.Environment()

    main_labs_list = get_stations_list(env=env, station_type="Main Lab")
    main_dr_room = get_stations_list(env=env, station_type="Main Doctor's Room")[0]
    main_bed = get_stations_list(env=env, station_type="Main Beds")[0]
    
    ft_labs_list = get_stations_list(env=env, station_type="Fast Track Lab")
    ft_dr_room = get_stations_list(env=env, station_type="Fast Track Doctor's Room")[0]
        
    # Create a new simulation environment
    ED = EmergencyDepartment(env, main_labs=main_labs_list, main_dr_room=main_dr_room, main_bed=main_bed, ft_labs=ft_labs_list, ft_dr_room=ft_dr_room)

    # Run the simulation
    ED.run()

    # Store queue data for plotting
    queue_df_list = []
    busy_df_list = []
    for station in ED.main_labs + ED.ft_labs + [ED.main_dr_room, ED.ft_dr_room, ED.main_bed]:
        queue_df_list.append(pd.DataFrame(station.queue_length_log))
        busy_df_list.append(pd.DataFrame(station.busy_staff_log))
        #st.write(station.queue_length_log)

    # Combine all data into a single DataFrame
    queue_df = pd.concat(queue_df_list)
    busy_df = pd.concat(busy_df_list)
    print(queue_df)
    print(busy_df)

    # Streamlit app content for the ED page
    st.subheader("📊 Emergency Department Simulation Results")

    # Display a message explaining the simulation
    st.write(
        "This page displays the queue length over time for various stations in the Emergency Department. "
        "You can use this visualization to track the workload at each station during the simulation."
    )

    # Plotting the queue length data using Plotly
    fig_queue = px.line(queue_df, x='Time', y='Queue Length', color='Station', title="Queue Length at Each Station Over Time")
    st.plotly_chart(fig_queue)

    # Plotting the busy staff data using Plotly
    fig_busy = px.line(busy_df, x='Time', y='Busy Staff', color='Station', title="Number of Busy Staff at Each Station Over Time")
    st.plotly_chart(fig_busy)