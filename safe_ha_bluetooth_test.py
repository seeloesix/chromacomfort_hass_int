"""
Safe Home Assistant Bluetooth Test Script

This script can be executed via the Home Assistant Developer Tools -> Template
to safely test Bluetooth discovery without SSH or breaking supervisor.

Instructions:
1. Copy this entire script content
2. Go to Developer Tools -> Template in Home Assistant UI  
3. Paste this in the template editor and click "Render"
4. Check the results to see what Bluetooth devices are discovered

This is the safest way to debug without risking supervisor issues.
"""

# This template can be used in Home Assistant Developer Tools
TEMPLATE_CODE = '''
{%- set ns = namespace(devices=[], chromacomfort_devices=[]) -%}
{%- for device_info in integration_entities("bluetooth") -%}
  {%- set ns.devices = ns.devices + [device_info] -%}
{%- endfor -%}

=== ChromaComfort Bluetooth Discovery Test ===
Total Bluetooth entities: {{ integration_entities("bluetooth") | length }}

{%- for device in integration_entities("bluetooth") -%}
  {%- set device_state = states[device] -%}
  {%- if device_state -%}
Device {{ loop.index }}:
  Entity: {{ device }}
  Name: {{ device_state.name }}
  State: {{ device_state.state }}
  Address: {{ device_state.attributes.get('address', 'N/A') }}
  RSSI: {{ device_state.attributes.get('rssi', 'N/A') }}
  
  {%- set device_name = device_state.name | lower -%}
  {%- set is_chromacomfort = 'chromacomfort' in device_name or 'chroma-comfort' in device_name or ('chroma' in device_name and 'comfort' in device_name) -%}
  ChromaComfort Match: {{ is_chromacomfort }}
  {%- if is_chromacomfort -%}
  *** CHROMACOMFORT DEVICE FOUND! ***
  {%- endif %}

  {%- endif -%}
{%- endfor -%}

=== Alternative Method: Check Bluetooth Service ===
Bluetooth Integration Active: {{ states.sensor | selectattr('entity_id', 'match', '.*bluetooth.*') | list | length > 0 }}
'''

print("=== SAFE HOME ASSISTANT BLUETOOTH TEST ===")
print()
print("This script provides a template you can use in Home Assistant Developer Tools.")
print("This is the safest method that won't risk breaking supervisor.")
print()
print("INSTRUCTIONS:")
print("1. Copy the template code below")
print("2. Go to Home Assistant UI -> Developer Tools -> Template")
print("3. Paste the template and click 'Render'")
print("4. Look for 'CHROMACOMFORT DEVICE FOUND!' in the results")
print()
print("TEMPLATE TO COPY:")
print("=" * 60)
print(TEMPLATE_CODE)
print("=" * 60)
print()
print("If the template method doesn't show Bluetooth devices,")
print("your fan might not be discovered by Home Assistant's Bluetooth integration.")