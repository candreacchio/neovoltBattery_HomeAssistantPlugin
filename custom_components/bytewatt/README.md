# ByteWatt Home Assistant Integration

This is a custom integration for Home Assistant that connects to ByteWatt/Neovolt battery systems.

## Automatic Recovery System

This integration includes an automatic recovery system to handle cases where the connection to the ByteWatt API becomes stuck or stops responding. The system provides:

1. **Heartbeat Monitoring**: The integration checks every 2 minutes to ensure data is being received properly.

2. **Stale Data Detection**: If no new data has been received for 5 minutes (configurable), the system will mark the data as stale.

3. **Automatic Recovery**: After detecting stale data for three consecutive checks, the system will automatically:
   - Reset the API client connection
   - Force re-authentication with the ByteWatt servers
   - Refresh all sensor data
   - Log the recovery process to Home Assistant logs

4. **Smart Retry Logic**: If recovery fails, the system will retry with increasing frequency using exponential backoff.

5. **Manual Recovery**: If needed, you can manually trigger the recovery process using the `bytewatt.force_reconnect` service from Developer Tools > Services in Home Assistant.

## Troubleshooting

If you notice the integration is not updating or showing stale data:

1. Check your internet connection
2. Verify the ByteWatt/Neovolt system is online
3. Use the `bytewatt.force_reconnect` service to manually trigger a reconnection
4. Check Home Assistant logs for any error messages
5. If problems persist, try restarting Home Assistant

## Configuration

Configure the integration through the Home Assistant UI:

1. Go to Configuration > Integrations
2. Click the "+ Add Integration" button
3. Search for "ByteWatt"
4. Enter your ByteWatt/Neovolt account credentials

## Services

This integration provides several services to control your battery system:

- **bytewatt.force_reconnect**: Force reconnect to the API when it appears stuck
- **bytewatt.update_battery_settings**: Update multiple battery settings at once
- **bytewatt.set_discharge_start_time**: Set when battery discharge should start
- **bytewatt.set_discharge_time**: Set when battery discharge should end
- **bytewatt.set_charge_start_time**: Set when battery charging should start
- **bytewatt.set_charge_end_time**: Set when battery charging should end
- **bytewatt.set_minimum_soc**: Set the minimum battery state of charge

For more details on each service, see the Services tab in Developer Tools.