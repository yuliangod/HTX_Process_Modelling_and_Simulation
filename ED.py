import random
from typing import Literal

import simpy

env = simpy.Environment()

PATIENT_INTERARRIVAL_DIST = lambda: random.expovariate(1 / 5)
TREATMENT_TIME_DIST = lambda: random.expovariate(1 / 3)
PROB_PATIENT_FAST_TRACK = 0.7


class EmergencyDepartment:
    def __init__(self, env):
        self.env = env
        
        # main track environment set-up
        self.main_labs = [
            Station(env=self.env, num_staff=1, name="Main Lab 1", treatment_time_dist=TREATMENT_TIME_DIST, prob_station_needed=1),
            Station(env=self.env, num_staff=1, name="Main Lab 2", treatment_time_dist=TREATMENT_TIME_DIST, prob_station_needed=0.5),
            Station(env=self.env, num_staff=1, name="Main Lab 3", treatment_time_dist=TREATMENT_TIME_DIST, prob_station_needed=0.5),
            Station(env=self.env, num_staff=1, name="Main Lab 4", treatment_time_dist=TREATMENT_TIME_DIST, prob_station_needed=0.5),
        ]
        self.main_dr_room = Station(env=self.env, num_staff=1, name="Main Doctor's Room", treatment_time_dist=TREATMENT_TIME_DIST, prob_station_needed=0.5)
        self.main_bed = Station(env=self.env, num_staff=3, name="Main Beds", treatment_time_dist=TREATMENT_TIME_DIST, prob_station_needed=0)
        
        # fast track environment set-up
        self.ft_labs = [
            Station(env=self.env, num_staff=1, name="FT Lab 1", treatment_time_dist=TREATMENT_TIME_DIST, prob_station_needed=1),
        ]
        self.ft_dr_room = Station(env=self.env, num_staff=1, name="FT Doctor's Room", treatment_time_dist=TREATMENT_TIME_DIST, prob_station_needed=0.5)
        self.ft_bed = Station(env=self.env, num_staff=3, name="FT Beds", treatment_time_dist=TREATMENT_TIME_DIST, prob_station_needed=0)

    def run(self):
        self.env.process(self.spawn_patients())  # Continuously spawn patients
        self.env.run(until=1000)  # Run simulation for 20 time units

    def spawn_patients(self):
        """Spawns a new patient every interarrival time."""
        patient_num = 1
        while True:
            if random.random() < PROB_PATIENT_FAST_TRACK:
                # spawn fast track patient
                patient = Patient(env=self.env, patient_num=patient_num, type='FT')
                # make patient go through ED processes
                self.env.process(patient.process(labs=self.ft_labs, dr_room=self.ft_dr_room, bed=self.ft_bed))
            else:
                # spawn main track patient
                patient = Patient(env=self.env, patient_num=patient_num, type='Main')
                # make patient go through ED processes
                self.env.process(patient.process(labs=self.main_labs, dr_room=self.main_dr_room, bed=self.main_bed))
                
            interarrival_time = PATIENT_INTERARRIVAL_DIST()
            yield self.env.timeout(interarrival_time)
            patient_num += 1


class Station:
    def __init__(self, env, num_staff, name="Lab1", treatment_time_dist=random.expovariate(1 / 5), prob_station_needed=1.0):
        self.env = env
        self.staff = simpy.Resource(env, capacity=num_staff)
        self.name = name
        self.treatment_time_dist = treatment_time_dist
        self.prob_station_needed = prob_station_needed
        
    def treatment(self, patient_num):
        with self.staff.request() as req:
            yield req  # Wait for resource availability

            print(f"Time {self.env.now}: Patient {patient_num} started treatment at {self.name}")
            treatment_duration = self.treatment_time_dist()
            yield self.env.timeout(treatment_duration)
            print(f"Time {self.env.now}: Patient {patient_num} finished treatment at {self.name}")


class Patient:
    def __init__(self, env, patient_num, type: Literal["FT", "Main"] = "FT"):
        self.env = env
        self.num = patient_num
        self.type = type

    def process(self, labs:list[Station], dr_room:Station, bed:Station):
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
        prob_bed_needed = dr_room.prob_station_needed
        
        if (random.random() < prob_bed_needed) & (self.type == "Main"):
            # if patient type is 'Main' and bed stay needed
            print(f"Bed stay needed for Patient {self.num}")
            yield self.env.process(self.go_to_station(bed))
        else:
            # if patient type is 'FT', no bed stay needed at all
            print(f"No bed stay needed for Patient {self.num} of type '{self.type}', discharged from ED")
        

    def go_to_station(self, station):
        """Send patient to a station for treatment."""
        print(f"Queue length at {station.name}: {len(station.staff.queue)}")
        yield self.env.process(station.treatment(patient_num = self.num))


if __name__ == "__main__":
    ED = EmergencyDepartment(env=env)
    ED.run()