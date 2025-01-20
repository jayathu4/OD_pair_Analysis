import pandas as pd
import networkx as nx
from typing import List, Dict, Optional, Any, Tuple

class RailReplacementRouteOptimizer:
    def __init__(self, csv_file: str):
        """
        Initialize the route optimizer with travel time data
        
        Args:
            csv_file (str): Path to the CSV file containing route data
        """
        self.df = pd.read_csv(csv_file)
        self.graph = self._build_route_graph()
        
    def _build_route_graph(self) -> nx.DiGraph:
        """
        Build a directed graph from the route data
        
        Returns:
            nx.DiGraph: A directed graph of routes and stations
        """
        G = nx.DiGraph()
        
        for _, row in self.df.iterrows():
            # Add edge with travel time as weight
            G.add_edge(
                row['From Station Name'], 
                row['To Station Name'], 
                weight=row['duration'], 
                route=row['Route'],
                direction=row['Direction']
            )
        
        return G
    
    def find_optimal_route(
        self, 
        origin: str, 
        destination: str, 
        transfer_penalty: float = 10.0
    ) -> Optional[Dict[str, Any]]:
        """
        Find the optimal route between origin and destination
        
        Args:
            origin (str): Starting station
            destination (str): Ending station
            transfer_penalty (float): Time penalty for route transfers
        
        Returns:
            Dict with route details or None if no route found
        """
        # Validate stations exist in the graph
        if origin not in self.graph.nodes or destination not in self.graph.nodes:
            return None
        
        # Find all possible paths
        possible_routes = []
        
        # Direct route check
        try:
            direct_paths = list(nx.all_simple_paths(self.graph, origin, destination))
            
            for path in direct_paths:
                # Calculate total travel time for the path
                total_time = sum(
                    self.graph[path[i]][path[i+1]]['weight'] 
                    for i in range(len(path)-1)
                )
                
                # Track routes and directions used
                route_details = [
                    {
                        'route': self.graph[path[i]][path[i+1]]['route'],
                        'direction': self.graph[path[i]][path[i+1]]['direction'],
                        'from_station': path[i],
                        'to_station': path[i+1],
                        'travel_time': self.graph[path[i]][path[i+1]]['weight']
                    } 
                    for i in range(len(path)-1)
                ]
                
                # Identify route variations (direct vs. multi-route)
                unique_routes = set(detail['route'] for detail in route_details)
                
                # Add a penalty for routes with transfers
                if len(unique_routes) > 1:
                    total_time += transfer_penalty * (len(unique_routes) - 1)
                
                possible_routes.append({
                    'total_time': total_time,
                    'path': path,
                    'route_details': route_details,
                    'unique_routes': list(unique_routes)
                })
        
        except nx.NetworkXNoPath:
            return None
        
        # Sort routes by total travel time
        if possible_routes:
            optimal_route = min(possible_routes, key=lambda x: x['total_time'])
            return {
                'total_travel_time': optimal_route['total_time'],
                'stations_path': optimal_route['path'],
                'route_details': optimal_route['route_details'],
                'unique_routes': optimal_route['unique_routes']
            }
        
        return None

def main():
    # Example usage
    optimizer = RailReplacementRouteOptimizer(r"C:\Users\jshanmugam\OneDrive - Transport for NSW\01. PYTHON_SCRIPTS\NetworkX - Graphs\CONFIG 13 _Testing\Travel_time_data_for_config13.csv")
    
    # Example route finding
    result = optimizer.find_optimal_route('Merrylands Station', 'Olympic Park Station')


    if result:
        print("Optimal Route Found:")
        print(f"Total Travel Time: {result['total_travel_time']} minutes")
        print("Stations Path:")
        for station in result['stations_path']:
            print(station)
        print("\nRoute Details:")
        for detail in result['route_details']:
            print(f"Route: {detail['route']} | Direction: {detail['direction']} | "
                  f"From: {detail['from_station']} | To: {detail['to_station']} | "
                  f"Travel Time: {detail['travel_time']} minutes")
        print(result)
    else:
        print("No route found.")

if __name__ == "__main__":
    main()
    
