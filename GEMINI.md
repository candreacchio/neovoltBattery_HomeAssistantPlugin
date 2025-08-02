# ByteWatt Home Assistant Integration Development Guide

## Repository Overview

This is a Home Assistant custom integration for monitoring and controlling ByteWatt/Neovolt battery systems. The integration provides comprehensive real-time monitoring of solar, battery, and grid power flows with sophisticated recovery mechanisms and battery control capabilities.

### Current Status
- **Version**: 1.0.0 (HACS compatible)
- **Architecture**: Production-ready with robust error handling and automatic recovery
- **Recent Cleanup**: Technical debt removed, modular architecture implemented (2024-12)

## Project Structure

```
custom_components/bytewatt/
├── __init__.py                 # Main integration entry point & services
├── bytewatt_client.py         # High-level API wrapper
├── config_flow.py             # Configuration UI flow
├── const.py                   # Constants and configuration
├── coordinator.py             # Data update coordinator with recovery
├── models.py                  # Data models for the integration
├── sensor.py                  # All sensor entity definitions
├── services.yaml              # Service definitions for Home Assistant
├── validation.py              # Minimal data validation (cleaned up)
├── manifest.json              # Integration metadata
├── translations/
│   └── en.json               # English translations
├── api/                      # Low-level API clients
│   ├── __init__.py
│   ├── neovolt_auth.py       # Authentication handling
│   ├── neovolt_client.py     # Core API client with async methods
│   └── settings.py           # Battery settings API
└── utilities/                # Utility modules (new modular architecture)
    ├── __init__.py
    ├── circuit_breaker.py    # Circuit breaker pattern implementation
    ├── connection_stats.py   # Connection health statistics
    ├── diagnostic_service.py # Health checks and diagnostics
    └── time_utils.py         # Time manipulation utilities
```

## Commands
- **Manual Install**: Copy `custom_components/bytewatt` to Home Assistant's `custom_components` directory
- **Lint**: `flake8 custom_components/bytewatt --max-line-length=100`
- **Type Check**: `mypy custom_components/bytewatt --ignore-missing-imports`
- **Validate**: `hass-config-check custom_components/bytewatt`
- **Debug**: Add to HA configuration.yaml: `logger: default: debug`
- **Syntax Check**: `python3 -m py_compile custom_components/bytewatt/**/*.py`

## Code Style
- **Python**: Version 3.9+ compatible
- **Formatting**: 4 spaces (not tabs), <100 char lines
- **Imports**: Standard lib → Third party → Home Assistant, grouped with blank lines
- **Naming**: CamelCase (classes), UPPER_CASE (constants), snake_case (variables/functions)
- **Error handling**: Try/except with appropriate logging levels
- **Comments**: Docstrings with triple double quotes
- **Type hints**: Required for all new functions/methods
- **Magic Numbers**: Use named constants from `const.py`

## Architecture

### Core Components
- **`bytewatt_client.py`**: High-level async API wrapper with battery control methods
- **`coordinator.py`**: DataUpdateCoordinator with circuit breaker pattern and automatic recovery
- **`sensor.py`**: All sensor entities (50+ sensors for comprehensive monitoring)
- **`config_flow.py`**: UI configuration flow with validation
- **`const.py`**: All constants, defaults, and configuration keys

### API Layer (`api/`)
- **`neovolt_client.py`**: Low-level async HTTP client with authentication
- **`neovolt_auth.py`**: Password encryption and authentication logic
- **`settings.py`**: Battery settings API with validation and retry logic

### Utility Modules (`utilities/`)
- **`circuit_breaker.py`**: Implements circuit breaker pattern for API resilience
- **`connection_stats.py`**: Tracks connection health and response times
- **`diagnostic_service.py`**: Health checks, diagnostics, and logging
- **`time_utils.py`**: Time format validation and manipulation

### Key Features
1. **Real-time Monitoring**: Battery SOC, power flows, energy statistics
2. **Daily Statistics**: PV generation, consumption, self-sufficiency metrics
3. **Battery Control**: Charge/discharge scheduling, minimum SOC setting
4. **Automatic Recovery**: Circuit breaker pattern with exponential backoff
5. **Health Monitoring**: Comprehensive diagnostics and connectivity checks
6. **HACS Compatible**: Installable through Home Assistant Community Store

### Services Available
- `bytewatt.set_discharge_time` - Set battery discharge end time
- `bytewatt.set_discharge_start_time` - Set battery discharge start time  
- `bytewatt.set_charge_start_time` - Set battery charge start time
- `bytewatt.set_charge_end_time` - Set battery charge end time
- `bytewatt.set_minimum_soc` - Set minimum state of charge
- `bytewatt.update_battery_settings` - Update multiple settings at once
- `bytewatt.force_reconnect` - Force API reconnection
- `bytewatt.health_check` - Run comprehensive health check
- `bytewatt.toggle_diagnostics` - Enable/disable diagnostic logging

### Configuration Options
- `scan_interval`: Data update frequency (default: 60s, min: 30s)
- `heartbeat_interval`: Health check frequency (default: 120s)
- `max_data_age`: Max age before data considered stale (default: 300s)
- `stale_checks_threshold`: Failed checks before recovery (default: 3)
- `notify_on_recovery`: Show recovery notifications (default: true)
- `diagnostics_mode`: Enable detailed logging (default: false)
- `auto_reconnect_time`: Daily reconnect time (default: "03:30:00")

## Recent Changes (December 2024)

### Technical Debt Cleanup
- ✅ **Removed 1000+ lines of disabled validation code** from `validation.py`
- ✅ **Split coordinator.py** (896 lines) into focused utility modules
- ✅ **Re-enabled battery control services** - API supports these features
- ✅ **Replaced magic numbers** with named constants
- ✅ **Cleaned up imports** and standardized error logging

### API Updates
- ✅ **Updated to new settings API endpoints**:
  - **GET**: `api/iterate/sysSet/getChargeConfigInfo?id=` (retrieve settings)
  - **POST**: `api/iterate/sysSet/updateChargeConfigInfo` (update settings)
- ✅ **Simplified device handling**: Using `id=""` (empty) to apply to all devices
- ✅ **New API data format**: Updated to use `timeChaf1`, `batUseCap`, `gridCharge`, etc.
- ✅ **Removed old API support**: Legacy endpoints no longer supported

### Battery Settings API Format

**GET Settings** (`getChargeConfigInfo?id=`):
```json
{
  "code": 200,
  "msg": "Success", 
  "data": {
    "gridCharge": 0,
    "timeChaf1": "14:30",
    "timeChae1": "16:00",
    "ctrDis": 0,
    "timeDisf1": "16:00", 
    "timeDise1": "06:00",
    "batUseCap": 6,
    "batHighCap": 100
  }
}
```

**POST Settings** (`updateChargeConfigInfo`):
```json
{
  "id": "",
  "gridCharge": 0,
  "timeChaf1": "14:30",
  "timeChae1": "16:00",
  "ctrDis": 0,
  "timeDisf1": "16:00",
  "timeDise1": "06:00",
  "batUseCap": 6,
  "batHighCap": 100,
  "batCapRange": [5, 100],
  "isJapaneseDevice": false,
  "upsReserveEnable": true,
  "chargeModeSetting": 0
}
```

### New Modular Architecture
- **Circuit Breaker Pattern**: `utilities/circuit_breaker.py` - Prevents API flooding during outages
- **Connection Statistics**: `utilities/connection_stats.py` - Tracks API health metrics
- **Diagnostic Service**: `utilities/diagnostic_service.py` - Health checks and troubleshooting
- **Improved Error Handling**: Exponential backoff, proper exception types

### Battery Control Features (Re-enabled)
- All battery control services now functional (previously disabled)
- Async battery settings API with validation and retry logic
- Support for charge/discharge time scheduling and minimum SOC
- Proper error handling and user feedback

## Testing & Validation

### Test Data Structure
```
TestData/
├── comparison_results/        # Validator comparison outputs
├── validatedJsonFiles/        # Known good data samples
└── [various validators]       # Historical validation scripts
```

### Validation Strategy
- **Basic Validation**: SOC range checks, required field validation
- **API Response Validation**: Server-side data is trusted as accurate
- **Retry Logic**: Exponential backoff for transient failures
- **Circuit Breaker**: Prevents cascading failures during outages

## Development Notes

### Adding New Sensors
1. Define sensor type constant in `const.py`
2. Add sensor configuration in `sensor.py`
3. Update `coordinator.py` if new data extraction needed
4. Add translations in `translations/en.json`

### Adding New Services
1. Define service constant in `const.py`
2. Add service handler in `__init__.py`
3. Define service schema in `services.yaml`
4. Update client methods if API changes needed

### Error Handling Best Practices
- Use specific exception types from API layers
- Log at appropriate levels (debug/info/warning/error)
- Implement retry logic with exponential backoff
- Use circuit breaker for external API calls
- Provide meaningful error messages to users

### Performance Considerations
- Minimum scan interval: 30 seconds (to prevent API abuse)
- Connection pooling for HTTP requests
- Efficient data structures for historical tracking
- Automatic cleanup of diagnostic logs (max 100 entries)