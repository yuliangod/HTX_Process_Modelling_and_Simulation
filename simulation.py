import random
from typing import Literal, Optional

import pandas as pd
import plotly.express as px
import simpy

PATIENT_INTERARRIVAL_DIST = lambda: random.expovariate(1 / 5)
TREATMENT_TIME_DIST = lambda: random.expovariate(1 / 3)
PROB_PATIENT_FAST_TRACK = 0.8

class Station:
    def __init__(self, num_staff, name="Lab1", treatment_time_dist=random.expovariate(1 / 5), prob_station_needed=1.0):
        self._env = None  # Initially set to None
        self.num_staff = num_staff
        self.name = name
        self.treatment_time_dist = treatment_time_dist
        self.prob_station_needed = prob_station_needed
        self.queue_length_log = []  # Store queue length over time
        self.busy_staff = 0  # Track number of busy staff
        self.busy_staff_log = []  # Log of busy staff over time
        
    def reset_station(self):
        self._env = None  # Initially set to None
        self.queue_length_log = []  # Store queue length over time
        self.busy_staff = 0  # Track number of busy staff
        self.busy_staff_log = []  # Log of busy staff over time
        
    @property
    def env(self):
        return self._env

    @env.setter
    def env(self, new_env):
        if new_env is not None and not isinstance(new_env, simpy.Environment):
            raise TypeError("env must be a simpy.Environment or None")
        self._env = new_env
        if self._env:  # Only create the resource if env is set
            self.staff = simpy.Resource(self._env, capacity=self.num_staff)  # Adjust staff capacity as needed
    
    def treatment(self, patient_num):
        if self.env is None:
            raise RuntimeError("Environment is not set. Please assign a valid simpy.Environment before calling treatment.")
        
        with self.staff.request() as req:
            self.log_queue_length()  # Log queue before patient gets treatment
            yield req  # Wait for resource availability
            
            self.log_queue_length()  # Log queue after patient gets treatment
            
            # Increase busy staff count
            self.busy_staff += 1
            self.log_busy_staff()

            print(f"Time {self.env.now}: Patient {patient_num} started treatment at {self.name}")
            treatment_duration = self.treatment_time_dist()
            yield self.env.timeout(treatment_duration)
            print(f"Time {self.env.now}: Patient {patient_num} finished treatment at {self.name}")
            
            # Decrease busy staff count
            self.busy_staff -= 1
            self.log_busy_staff()
            
    def log_busy_staff(self):
        """Log the number of busy staff at the current time"""
        log_entry = {"Station": self.name, "Time": self.env.now, "Busy Staff": self.busy_staff}
        self.busy_staff_log.append(log_entry)
    
    def log_queue_length(self):
        """Log queue length at current time"""
        self.queue_length_log.append({"Station":self.name, "Time":self.env.now, "Queue Length":len(self.staff.queue)})

class Patient:
    def __init__(self, env, patient_num, type: Literal["FT", "Main"] = "FT"):
        self.env = env
        self.num = patient_num
        self.type = type

    def process(self, labs:list[Station], dr_room:Station, bed:Optional[Station]=None):
        """Process a patient through all labs sequentially."""
        print(f"Time {self.env.now}: Patient {self.num} of type '{self.type}' arrives in ED")
        for i, lab in enumerate(labs):
            prob_lab_needed = lab.prob_station_needed
            # if lab needed (assume first lab is compulsory for all patients)
            if (random.random() < prob_lab_needed) | (i == 0):
                print(f"Further lab testing required for Patient {self.num}, heading over to {lab.name}")
                yield self.env.process(self.go_to_station(lab))
            else:
                print(f"No further lab treatment needed for Patient {self.num} of type '{self.type}', heading over to Doctor's Room now")
                break
                
        yield self.env.process(self.go_to_station(dr_room))
        
        if self.type == "Main":
            prob_bed_needed = bed.prob_station_needed
            if random.random() < prob_bed_needed:
                # if patient type is 'Main' and bed stay needed
                print(f"Bed stay needed for Patient {self.num}")
            yield self.env.process(self.go_to_station(bed))
        else:
            # if patient type is 'FT', no bed stay needed at all
            print(f"No bed stay needed for Patient {self.num} of type '{self.type}', discharged from ED")
        

    def go_to_station(self, station):
        """Send patient to a station for treatment."""
        #station.log_queue_length()  # Log queue before patient enters
        print(f"Queue length at {station.name}: {len(station.staff.queue)}")
        yield self.env.process(station.treatment(patient_num = self.num))
        
class EmergencyDepartment:
    def __init__(self, env, main_labs:Station, main_dr_room:list[Station], main_bed:list[Station], ft_labs:Station, ft_dr_room, prob_patient_fast_track, patient_interarrival_dist):
        self.env = env
        
        # set environment
        for station in main_labs + ft_labs + [main_dr_room, ft_dr_room, main_bed]:
            station.env = self.env
        
        # main track environment set-up
        self.main_labs = main_labs
        self.main_dr_room = main_dr_room
        self.main_bed = main_bed
        
        # fast track environment set-up
        self.ft_labs = ft_labs
        self.ft_dr_room = ft_dr_room
        
        # patient environment set-up
        self.prob_patient_fast_track = prob_patient_fast_track
        self.patient_interarrival_dist = patient_interarrival_dist

    def run(self, until):
        self.env.process(self.spawn_patients())  # Continuously spawn patients
        self.env.run(until=until)  # Run simulation for n time units

    def spawn_patients(self):
        """Spawns a new patient every interarrival time."""
        patient_num = 1
        while True:
            if random.random() < self.prob_patient_fast_track:
                # spawn fast track patient
                patient = Patient(env=self.env, patient_num=patient_num, type='FT')
                # make patient go through ED processes
                self.env.process(patient.process(labs=self.ft_labs, dr_room=self.ft_dr_room))
            else:
                # spawn main track patient
                patient = Patient(env=self.env, patient_num=patient_num, type='Main')
                # make patient go through ED processes
                self.env.process(patient.process(labs=self.main_labs, dr_room=self.main_dr_room, bed=self.main_bed))
                
            interarrival_time = self.patient_interarrival_dist()
            yield self.env.timeout(interarrival_time)
            patient_num += 1


if __name__ == "__main__":
    env = simpy.Environment()
    
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
    
    ED = EmergencyDepartment(env=env, main_labs=main_labs, main_dr_room=main_dr_room, main_bed=main_bed, ft_labs=ft_labs, ft_dr_room=ft_dr_room, prob_patient_fast_track=PROB_PATIENT_FAST_TRACK, patient_interarrival_dist=PATIENT_INTERARRIVAL_DIST)
    ED.run(until=1000)
    
    # Store queue data for plotting
    queue_df_list = []
    busy_df_list = []
    for station in ED.main_labs + ED.ft_labs + [ED.main_dr_room, ED.ft_dr_room, ED.main_bed]:
        queue_df_list.append(pd.DataFrame(station.queue_length_log))
        busy_df_list.append(pd.DataFrame(station.busy_staff_log))
        
    # Combine all data into a single DataFrame
    queue_df = pd.concat(queue_df_list)
    busy_df = pd.concat(busy_df_list)
    print(queue_df)
    print(busy_df)

