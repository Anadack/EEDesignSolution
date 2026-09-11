# EE Composer Generator v5.7

## Scope
This version integrates EEC schema-aligned object creation based on the public structures from the provided headers.

## Main capabilities
- Create EEC-aligned JSON objects from scratch: system, component, sensor, actuator, ECU, ECU pin, bus, bundle, signal group.
- Clone an existing selected object from the library or architecture.
- Edit and export each object independently.
- Add/edit/remove signals, pins, and connectors.
- Export normalization recomputes count/capacity fields before download/save.
- Create new JSON files in a linked library folder when browser write access is available.
- Keep resizable panes, resizable logs, and resizable JSON modal.

## Alignment notes
- Signal fields include name, part_number, priority, safety, type, interface_type, unit, min_value, max_value, resolution, scaling, is_mapped, digital_structure.
- Device pins include role, interface_type, electrical_requirement, current/voltage/diagnostic/safety/supply fields.
- Connectors include family, gender, cavities, sealing, rating, IP, temperature fields.
- Systems/components/devices/ECUs include variant_id, obsolete, owner refs as JSON-safe IDs/null, arrays and count/capacity fields.
