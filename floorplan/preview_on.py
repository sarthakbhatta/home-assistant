import re, sys
svg = open('iso.svg').read()
LIGHTS = ['light.office_downlight_1','light.office_downlight_2','light.office_bathroom_downlight',
          'light.bedroom_downlight_1','light.wiz_tunable_white_cdad76',
          'light.wiz_tunable_white_cdadae','light.wiz_tunable_white_9cde0f']
PLUGS = ['switch.office_main_desk','switch.laptop_office','switch.coffee_machine_switch',
         'switch.tuya_wall_socket_socket_1','switch.tuya_wall_socket_socket_2',
         'media_player.jio_set_top_box','siren.hub']
VALVES = ['valve.tuya_automated_watering_valve_1','valve.tuya_automated_watering_valve_2']
add = {}
for l in LIGHTS: add[l]='light-on'; add[l+'-pool']='light-on'
add['light.smart_light_strip1']='light-on'
for n in '123': add['light.st'+n]='light-on'; add['light.st%s-pool'%n]='light-on'
add['light.master_bedroom_led_inner']='light-on'; add['light.master_bedroom_led_outer']='light-on'
add['climate.panasonic_ac_panasonic_ac']='ac-on'; add['climate.panasonic_ac_panasonic_ac-fan']='ac-running'
for p in PLUGS: add[p]='plug-on'
add['switch.office_main_desk-bolt']='plug-on'
for k in ['switch.borewell_motor','switch.borewell_motor-ring','switch.borewell_motor-hub']: add[k]='pump-on'
add['binary_sensor.terrace_door_sensor_door']='door-open'
add['binary_sensor.motion_sensor_motion']='motion-on'; add['motion-fx']='motion-on'
for v in VALVES: add[v]='valve-open'; add[v+'-spray']='valve-open'; add[v+'-jets']='valve-open'
add['mon-screen']='on'; add['media_player.samsung_7_series_50_ua50nu7470']='on'
add['camera.hikvision_ds_2cd1043g0_i_mainstream-lens']='cam-on'
def inject(svg,eid,extra):
    m=re.search(r'id="%s"'%re.escape(eid),svg)
    if not m: return svg,False
    st=svg.rfind('<',0,m.start()); en=svg.find('>',m.end()); tag=svg[st:en]
    cm=re.search(r'class="([^"]*)"',tag)
    tag2 = tag[:cm.start(1)]+cm.group(1)+' '+extra+tag[cm.end(1):] if cm else tag+' class="%s"'%extra
    return svg[:st]+tag2+svg[en:],True
miss=[]
for e,c in add.items():
    svg,ok=inject(svg,e,c)
    if not ok: miss.append(e)
svg=re.sub(r'(<text id="office-temp"[^>]*>)--',r'\g<1>29.1°',svg)
open('iso_on.svg','w').write(svg)
print('injected',len(add)-len(miss),'missing',miss)
