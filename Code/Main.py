import streamlit as st
import os
import networkx as nx
import pandas as pd
import calc_functions as cf
from pathlib import Path
import time
import heapq




APP_TITLE = "OD Pairs Analysis"
st.set_page_config(page_title=APP_TITLE, layout="wide", page_icon=":oncoming_bus:")

@st.cache_data()
def load_data():
    stations_df = pd.read_csv(os.path.join(Path(os.getcwd()).parent, 'Supporting Data', 'Station_data_Latest.csv'))
    tt_dist_matrix = pd.read_csv(os.path.join(Path(os.getcwd()).parent, 'Supporting Data', 'tt_speed_matrix_for_stations.csv'))
    return stations_df, tt_dist_matrix

@st.cache_data()
def create_network():
    stations_df, tt_dist_matrix = load_data()
    stations_group = stations_df.groupby('Line_ID')
    train_lines = {}
    for line_id, df in stations_group:
        train_lines[line_id] = df['stop_name'].to_list()
    
    G = nx.MultiGraph()
    for _, station in stations_df.iterrows():
        G.add_node(station['stop_name'], pos=(station['Latitude'], station['Longitude']))
    for line, stations in train_lines.items():
        for i in range(len(stations) - 1):
            station_pair = f"{stations[i]} - {stations[i+1]}"
            duration = tt_dist_matrix[tt_dist_matrix['station_pair'] == station_pair]['duration_seconds'].values[0] if not tt_dist_matrix[tt_dist_matrix['station_pair'] == station_pair].empty else 300
            direction_ = tt_dist_matrix[tt_dist_matrix['station_pair'] == station_pair]['Direction'].values[0] if not tt_dist_matrix[tt_dist_matrix['station_pair'] == station_pair].empty else "NotFound"
            # print(stations[i], stations[i+1])
            # print(f"Adding edge: {stations[i]} -> {stations[i+1]}, line={line}, weight={duration}, direction={direction_}")
            G.add_edge(stations[i], stations[i+1], line=line, weight=duration, direction=direction_)
    return G

def get_directions(path):
    stations_df, tt_dist_matrix = load_data()
    direction_list = []
    for i in range(len(path)-1):
        station_pair = f"{path[i]} - {path[i+1]}"
        direction = tt_dist_matrix[tt_dist_matrix['station_pair'] == station_pair]['Direction'].values[0] if not tt_dist_matrix[tt_dist_matrix['station_pair'] == station_pair].empty else "NotFound"
        direction_list.append(direction)
    return direction_list


def main(): 
    st.title(APP_TITLE) 
    

    # Load the Stations and load the network
    st.write(Path(os.getcwd()).parent)
    G = create_network()
        
    stations_df, tt_dist_matrix = load_data()
    
    uploaded_file = st.file_uploader("Choose the extracted OD pairs file", type="csv")
    if uploaded_file is not None:
        od_pairs_df = pd.read_csv(uploaded_file)
        od_pairs_df = od_pairs_df.dropna(subset=['tap_off_tsn_name'])
        index_same_station = od_pairs_df[od_pairs_df['tap_on_tsn_name'] == od_pairs_df['tap_off_tsn_name']].index
        od_pairs_df = od_pairs_df.drop(index=index_same_station)
        od_pairs_df = cf.simplify_dataframe(od_pairs_df)
        
        
        # Remove stations that are not included in the network
        network_stations = list(G.nodes)
        index_to_drop = od_pairs_df[~od_pairs_df['tap_on_tsn_name'].isin(network_stations) | ~od_pairs_df['tap_off_tsn_name'].isin(network_stations)].index
        od_pairs_df = od_pairs_df.drop(index=index_to_drop)
        
        # Multiselect option for selecting the closed stations
        unique_stations = stations_df['stop_name'].unique().tolist()
        selected_closed_stations = st.multiselect("Select closed/affected stations", unique_stations)
        st.write(" <--> ".join(selected_closed_stations))
        
        # define the boundaries in both Inbound and Outbound direction
        inbound_col, outbound_col = st.columns(2)

        with inbound_col:
            st.subheader("Select the first station in Inbound direction")
            ib_boubndary_station = st.selectbox("Select the station", selected_closed_stations, key="ib_boubndary_station")

        with outbound_col:
            st.subheader("Select the first station in Outbound direction")
            ob_boundary_station = st.selectbox("Select the station", selected_closed_stations, key="ob_boundary_station")
        
        st.write (f"Inbound: {ib_boubndary_station} <--> Outbound: {ob_boundary_station}")
        if st.button("Calculate Result"):
            with st.spinner("Calculating fastest routes..."):
                od_pairs_df['fastest_route'] = od_pairs_df.apply(lambda x: cf.find_fastest_route(G, x['tap_on_tsn_name'], x['tap_off_tsn_name'], transfer_penalty=900), axis=1)
                od_pairs_df['affected_OD'] = od_pairs_df['fastest_route'].apply(lambda x: sum(station in x['path'] for station in selected_closed_stations) >= 2)
                od_pairs_df = od_pairs_df[od_pairs_df['affected_OD'] == True]
                od_pairs_df['path_type'] = od_pairs_df.apply(lambda x: cf.get_path_type(x['tap_on_tsn_name'], x['tap_off_tsn_name'], selected_closed_stations, x['fastest_route']['path']), axis=1)
                
            # st.write(od_pairs_df)
            od_pairs_df = od_pairs_df.reset_index(drop=True)
            fastes_path_df = pd.json_normalize(od_pairs_df['fastest_route'])
            od_pairs_df = od_pairs_df.drop(columns=['fastest_route']).join(fastes_path_df)
            od_pairs_df['new_origin'] = od_pairs_df.apply(lambda x: cf.calculate_origin_station(x['path_type'], x['tap_on_tsn_name'], ib_boubndary_station, ob_boundary_station, x['path']), axis=1)
            od_pairs_df['new_destination'] = od_pairs_df.apply(lambda x: cf.calculate_destination_station(x['path_type'], x['tap_off_tsn_name'], ib_boubndary_station, ob_boundary_station, x['path']), axis=1)
            
            od_pairs_df['new_origin'] = od_pairs_df.apply(lambda x: cf.origin_station_if_none(x['new_origin'], x['path'], selected_closed_stations), axis=1)
            od_pairs_df['new_destination'] = od_pairs_df.apply(lambda x: cf.destination_station_if_none(x['new_destination'], x['path'], selected_closed_stations), axis=1)
            
            od_pairs_df['directions'] = od_pairs_df.apply(lambda x: get_directions(cf.find_fastest_route(G, x['new_origin'], x['new_destination'])['path']), axis=1)
            od_pairs_df['direction'] = od_pairs_df['directions'].apply(lambda x: cf.max_count_directions(x))
            
            
            st.dataframe(od_pairs_df)
            st.write(od_pairs_df['segments'].iloc[0])
            
        

# Run the Streamlit app
if __name__ == "__main__":
    main()

