from influxdb import InfluxDBClient

client = InfluxDBClient('localhost', 8086, 'root', 'root', 'noisemapper')

print("Dropping unwanted 'demo-user' points...")
client.query("DROP SERIES FROM samples WHERE user_uuid='demo-user'")
print("Done!")

# Also just explicitly drop test=True in case any are stuck
print("Dropping test='True' points...")
client.query("DROP SERIES FROM samples WHERE test='True'")
print("Done!")
