import math

# Function to calculate distance using Haversine formula
fn haversine(lat1: Float64, lon1: Float64, lat2: Float64, lon2: Float64) -> Float64:
    let R = 6371.0  # Radius of Earth in kilometers
    let dlat = math.radians(lat2 - lat1)
    let dlon = math.radians(lon2 - lon1)
    
    let a = math.sin(dlat / 2) * math.sin(dlat / 2) + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) * math.sin(dlon / 2)
    let c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    
    return R * c  # Distance in km

# Read input data from Python
fn main():
    for line in std.io.stdin.read_lines():
        let parts = line.split(" ")
        let lat1 = Float64(parts[0])
        let lon1 = Float64(parts[1])
        let lat2 = Float64(parts[2])
        let lon2 = Float64(parts[3])
        
        let distance = haversine(lat1, lon1, lat2, lon2)
        print(distance)
