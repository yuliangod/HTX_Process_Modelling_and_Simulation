import math
import random

import numpy as np
import pandas as pd
import scipy.stats as stats
import simpy

from simulation import EmergencyDepartment, Station


class Analysis:
    def __init__(self):
        pass
    
    def run_analysis_stat(self, burn_in_period:int, confidence_level, num_iterations:int, main_labs, main_dr_room, main_bed, ft_labs, ft_dr_room, prob_patient_fast_track, patient_interarrival_dist, tol=0.5):
        # Run the batch simulations
        queue_df_list, busy_df_list, queue_bin_df_list, busy_bin_df_list, queue_mavg, busy_mavg = self.run_batch(
            num_iterations=num_iterations, 
            batch_run_size=burn_in_period*4, 
            main_labs=main_labs, 
            main_dr_room=main_dr_room, 
            main_bed=main_bed, 
            ft_labs=ft_labs, 
            ft_dr_room=ft_dr_room,
            prob_patient_fast_track=prob_patient_fast_track, 
            patient_interarrival_dist=patient_interarrival_dist,
        )
        
        queue_results_df = self.compile_stats_table(data_bin_df_list=queue_bin_df_list, burn_in_period=burn_in_period, confidence_level=confidence_level, tol=tol, num_iterations=num_iterations, target_col="Queue Length")
        busy_staff_results_df = self.compile_stats_table(data_bin_df_list=busy_bin_df_list, burn_in_period=burn_in_period, confidence_level=confidence_level, tol=tol, num_iterations=num_iterations, target_col="Busy Staff")

        return queue_results_df, busy_staff_results_df

    def compile_stats_table(self,  data_bin_df_list, burn_in_period, confidence_level, tol, num_iterations, target_col="Queue Length"):
        # Define a list to store the means of queue lengths for each station across all runs
        station_mean_values = {station: [] for queue_df in data_bin_df_list for station in queue_df['Station'].unique()}
        station_within_tol = {station: [] for queue_df in data_bin_df_list for station in queue_df['Station'].unique()}

        # Iterate over each DataFrame in data_bin_df_list
        for data_df in data_bin_df_list:
            # Filter out rows before the burn-in period
            data_df_filtered = data_df[data_df['Time'] >= burn_in_period]
            
            # Group the filtered DataFrame by 'Station' to calculate statistics for each station
            grouped = data_df_filtered.groupby('Station')
            
            # Loop over each station and calculate the mean queue length for each run
            for station, group in grouped:
                t_score = stats.t.ppf(1 - (1-confidence_level)/2, df=len(group)-1)
                se = group[target_col].std()
                within_tol = t_score*se < tol
                station_within_tol[station].append(within_tol)
                
                # Calculate the mean queue length for this station in this simulation run
                mean_queue_length = group[target_col].mean()
                
                # Store the mean queue length for this station in this run
                station_mean_values[station].append(mean_queue_length)

        # Now, calculate the overall mean and standard deviation of means for each station
        final_results = []
        for station, means in station_mean_values.items():
            # Calculate the mean of means across all runs
            mean_of_means = np.mean(means)
            
            # Calculate the standard deviation of the means across all runs
            std_of_means = np.std(means, ddof=1)  # Sample standard deviation (ddof=1)
            t_score = stats.t.ppf(1 - (1 - confidence_level) / 2, df=num_iterations-1)
            # Calculate the confidence interval using t-distribution
            margin_of_error = t_score * std_of_means
            ci_lower = mean_of_means - margin_of_error
            ci_upper = mean_of_means + margin_of_error
            
            # Store the results for this station
            final_results.append({
                "Station": station,
                "Mean of Means Queue Length": mean_of_means,
                "Standard Deviation of Means": std_of_means,
                "Average Queue Length Lower Bound": ci_lower,
                "Average Queue Length Upper Bound": ci_upper
            })
            
        # Convert station_within_tol into a DataFrame and apply .all() to check if all values are True for each station
        tol_df = pd.DataFrame(station_within_tol).all()

        # Assign a name to the Series
        tol_df.name = 'All Simulations Within Tolerance'

        # Join the tol_df (True/False) as a new column to the final_results DataFrame
        final_results_df = pd.DataFrame(final_results)
        final_results_df = final_results_df.set_index('Station').join(tol_df)

        return final_results_df
            
    def run_batch(self, num_iterations:int, batch_run_size:int, main_labs, main_dr_room, main_bed, ft_labs, ft_dr_room, prob_patient_fast_track, patient_interarrival_dist, mavg_list=[5,10]):
        queue_df_list = []
        busy_df_list = []
        queue_bin_df_list = []
        busy_bin_df_list = []
        for i in range(num_iterations):
            queue_df, busy_df, queue_bin_df, busy_bin_df = self.run_simulation(batch_run_size=batch_run_size, main_labs=main_labs, main_dr_room=main_dr_room, main_bed=main_bed, ft_labs=ft_labs, ft_dr_room=ft_dr_room, prob_patient_fast_track=prob_patient_fast_track, patient_interarrival_dist=patient_interarrival_dist,get_bin=True)
            
            queue_df_list.append(queue_df)
            busy_df_list.append(busy_df)
            queue_bin_df_list.append(queue_bin_df)
            busy_bin_df_list.append(busy_bin_df)
        
        queue_mavg = self.get_mavg(simulation_list=queue_bin_df_list, mavg_list=mavg_list)
        busy_mavg = self.get_mavg(simulation_list=busy_bin_df_list, mavg_list=mavg_list)
        
        return queue_df_list, busy_df_list, queue_bin_df_list, busy_bin_df_list, queue_mavg, busy_mavg
        
    def get_mavg(self, simulation_list: list[pd.DataFrame], mavg_list: list[int]):
        simulation_list = [df.set_index(["Time", "Station"]) for df in simulation_list]
        
        print(simulation_list)
        # Concatenate along columns and compute the mean across DataFrames
        average_df = pd.concat(simulation_list, axis=1).mean(axis=1).to_frame(name='Average')

        # Reset index for proper processing
        average_df = average_df.reset_index()

        # Compute moving averages for each station
        for mavg in mavg_list:
            average_df[f"MAVG {mavg}"] = (
                average_df.groupby("Station")["Average"]
                .rolling(mavg, min_periods=1)  # min_periods=1 ensures initial values are not NaN
                .mean()
                .reset_index(level=0, drop=True)  # Drop extra index from rolling
            )
            
        return average_df  # Return for further use
    
    def run_simulation(self, batch_run_size:int, main_labs, main_dr_room, main_bed, ft_labs, ft_dr_room, prob_patient_fast_track, patient_interarrival_dist, get_bin=False):
        for station in main_labs + ft_labs + [main_dr_room, ft_dr_room, main_bed]:
            station.reset_station()
        
        env = simpy.Environment()
    
        ED = EmergencyDepartment(env=env, main_labs=main_labs, main_dr_room=main_dr_room, main_bed=main_bed, ft_labs=ft_labs, ft_dr_room=ft_dr_room, prob_patient_fast_track=prob_patient_fast_track, patient_interarrival_dist=patient_interarrival_dist)
        ED.run(until=batch_run_size)
        
        A = Analysis()
        queue_df, busy_df = A.get_df(ED)
        
        if get_bin == False:
            return queue_df, busy_df
        else:
            queue_bin_df = A.bin_data(queue_df, until=batch_run_size, target_col="Queue Length")
            busy_bin_df = A.bin_data(busy_df, until=batch_run_size, target_col="Busy Staff")
            return queue_df, busy_df, queue_bin_df, busy_bin_df
    
    def get_df(self, ED:EmergencyDepartment):
        # Store queue data for plotting
        queue_df_list = []
        busy_df_list = []
        for station in ED.main_labs + ED.ft_labs + [ED.main_dr_room, ED.ft_dr_room, ED.main_bed]:
            queue_df_list.append(pd.DataFrame(station.queue_length_log))
            busy_df_list.append(pd.DataFrame(station.busy_staff_log))
            
        # Combine all data into a single DataFrame
        queue_df = pd.concat(queue_df_list)
        busy_df = pd.concat(busy_df_list)
        
        return queue_df, busy_df
    
    def bin_data(self, df:pd.DataFrame, until:int, target_col:str):
        # Define full time grid (every second from start to end)
        time_grid = pd.DataFrame({'Time': np.arange(0, until + 1)})

        # Get unique stations
        stations = df['Station'].unique()

        # Initialize list for storing results
        bin_dfs = []

        # Process each station separately
        for station in stations:
            station_df = df[df['Station'] == station]  # Filter data for current station
            
            # Round up time to nearest second and select last value
            station_df['Time'] = station_df['Time'].apply(math.ceil).astype(int)
            station_df = station_df.groupby('Time').last().reset_index()

            # Merge with the full time grid (ensure every second is present)
            station_bin_df = station_df.merge(time_grid, on='Time', how='right')

            # Fill missing station name
            station_bin_df['Station'] = station  # Assign station name explicitly

            # Forward-fill missing queue lengths
            station_bin_df[target_col] = station_bin_df[target_col].ffill()
            
            station_bin_df.set_index(["Time", "Station"])

            # Append to results list
            bin_dfs.append(station_bin_df)

        # Combine results for all stations
        bin_df = pd.concat(bin_dfs, ignore_index=True).fillna(0)
        bin_df[target_col] = bin_df[target_col].astype(int)

        return bin_df
    
if __name__ == "__main__":
    PATIENT_INTERARRIVAL_DIST = lambda: random.expovariate(1 / 5)
    TREATMENT_TIME_DIST = lambda: random.expovariate(1 / 3)
    PROB_PATIENT_FAST_TRACK = 0.8
    
    # define main track settings
    main_labs = [
            Station(num_staff=1, name="Main Lab 1", treatment_time_dist=TREATMENT_TIME_DIST, prob_station_needed=1),
            Station(num_staff=1, name="Main Lab 2", treatment_time_dist=TREATMENT_TIME_DIST, prob_station_needed=0.5),
            Station(num_staff=1, name="Main Lab 3", treatment_time_dist=TREATMENT_TIME_DIST, prob_station_needed=0.5),
            Station(num_staff=1, name="Main Lab 4", treatment_time_dist=TREATMENT_TIME_DIST, prob_station_needed=0.5),
        ]
    main_dr_room = Station(num_staff=1, name="Main Doctor's Room", treatment_time_dist=TREATMENT_TIME_DIST, prob_station_needed=1)
    main_bed = Station(num_staff=30, name="Main Beds", treatment_time_dist=lambda:random.expovariate(1 / 720), prob_station_needed=0.01)
    
    # define fast track settings
    ft_labs = [
            Station(num_staff=1, name="FT Lab 1", treatment_time_dist=TREATMENT_TIME_DIST, prob_station_needed=1),
        ]
    ft_dr_room = Station(num_staff=1, name="FT Doctor's Room", treatment_time_dist=TREATMENT_TIME_DIST, prob_station_needed=1)
    
    A = Analysis()
    
    #for i in range(3):
    #    queue_df, busy_df = A.run_simulation(batch_run_size=1000, main_labs=main_labs, main_dr_room=main_dr_room, main_bed=main_bed, ft_labs=ft_labs, ft_dr_room=ft_dr_room)
    #    print(busy_df)
    #queue_df_list, busy_df_list, queue_mavg, busy_mavg = A.run_batch(num_iterations=5, batch_run_size=1000, main_labs=main_labs, main_dr_room=main_dr_room, main_bed=main_bed, ft_labs=ft_labs, ft_dr_room=ft_dr_room)
    #print(busy_mavg)
    print(A.run_analysis_stat(burn_in_period=400, confidence_level=0.95, num_iterations=5, main_labs=main_labs, main_dr_room=main_dr_room, main_bed=main_bed, ft_labs=ft_labs, ft_dr_room=ft_dr_room, prob_patient_fast_track=PROB_PATIENT_FAST_TRACK, patient_interarrival_dist=PATIENT_INTERARRIVAL_DIST))