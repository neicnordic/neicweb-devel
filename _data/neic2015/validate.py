"""\
Check for inconsistencies and missing info in conference program data.
"""
import optparse
import os
import sys

import yaml
from __builtin__ import str

class Options(optparse.OptionParser):
    def __init__(self):
        global __doc__
        optparse.OptionParser.__init__(
            self, usage="%prog [options]",
            description=__doc__)
        self.add_option(
            '-d', '--datadir', action='store', default=os.path.dirname(__file__),
            help=("Program data directory."))

def usage(message):
    sys.stderr.write(message + "\n")
    sys.stderr.write(Options().get_usage())
    return os.EX_USAGE

def error(msg, *args, **kw):
    if args:
        msg %= args
    elif kw:
        msg %= kw
    raise ValueError(msg)

def _get(datadict, key, default=[]):
    return datadict.get(key, None) or default

datasets = [
    'persons',
    'program',
    'rooms',
    'sessions',
    'workshops',
    ]

def load_dataset(datadir, dataset):
    return yaml.load(open(os.path.join(datadir, dataset + '.yml')))

def load_data(datadir):
    event = dict()
    for dataset in datasets:
        event[dataset] = load_dataset(datadir, dataset)
    return event

### General purpose 

def assert_string_keys(label, datadict):
    for k in datadict.keys():
        if not isinstance(k, str):
            error("%s %r incorrect key type, must be a string.", label, k)

def assert_value_data_types(label, datadict, datatype, *keys):
    if not keys:
        keys = datadict.keys()
    for k in keys:
        value = datadict.get(k, None)
        if value and not isinstance(value, datatype):
            error("%s %s %r must be %s.", label, k, value, datatype)

def assert_item_data_types(label, datalist, datatype):
    for i, item in enumerate(datalist):
        if not isinstance(item, datatype):
            error("%s %s must be %s.", label, i + 1, datatype)

### Persons

def validate_persons(persons):
    assert_string_keys('Person', persons)
    for id, person in persons.items():
        assert_value_data_types('Person %r' % id, person, basestring)
        if not person.get('name', None):
            error("Person %r has no name.", id)

### Sessions

def assert_session_id(label, session):
    if not session.get('id', None):
        error("%s has no ID.", label)
    elif not isinstance(session['id'], str):
        error("%s ID must be type str.", label)
        
def validate_slides(label, slides):
    assert_item_data_types(label, slides, str)

def validate_panel(label, slides):
    assert_item_data_types(label, slides, basestring)

def validate_session_talk(label, talk):
    assert_string_keys(label, talk)
    assert_value_data_types(label, talk, str, 'speaker', 'title', 'abstract')
    assert_value_data_types(label, talk, list, 'slides', 'panel')
    validate_slides(label + ' slides', _get(talk, 'slides'))
    validate_panel(label + ' panel', _get(talk, 'panel'))

def validate_session_talks(label, talks):
    assert_item_data_types(label, talks, dict)
    for i, talk in enumerate(talks):
        talk_label = label + ' %s' % (i + 1)
        validate_session_talk(talk_label, talk)

def validate_sessions(sessions):
    assert_string_keys('Session', sessions)
    for id, session in sessions.items():
        label = 'Session %r' % id
        assert_string_keys(label, session)
        assert_value_data_types(label, session, basestring, 'title', 'chair', 'abstract')
        assert_value_data_types(label, session, list, 'talks')
        validate_session_talks(label + ' talk', _get(session, 'talks'))

### Workshops

def validate_workshop_chairs(label, chairs):
    assert_string_keys(label, chairs)
    assert_value_data_types(label, chairs, str)
        
def validate_workshops(workshops):
    assert_string_keys('Workshop', workshops)
    for id, workshop in workshops.items():
        label = 'Workshop %r' % id
        assert_string_keys(label, workshop)
        assert_value_data_types(label, workshop, basestring, 'room', 'title', 'abstract', 'agenda')
        assert_value_data_types(label, workshop, int, 'sessions')
        assert_value_data_types(label, workshop, dict, 'chair')
        assert_value_data_types(label, workshop, list, 'slides')
        validate_slides(label + ' slide', _get(workshop, 'slides'))
        validate_workshop_chairs(label + ' chair', _get(workshop, 'chair', {}))

### Program

def validate_schedule(label, schedule):
    assert_string_keys(label, schedule)
    assert_value_data_types(label, schedule, str)

def validate_day(label, day):
    assert_string_keys(label, day)
    assert_value_data_types(label, day, basestring, 'day')
    assert_value_data_types(label, day, int, 'parallel_sessions')
    if not day.get('parallel_sessions', 0) > 0:
        error("%s parallel_sessionss must be set > 0.", label)
    assert_value_data_types(label, day, dict, 'schedule')
    validate_schedule(label + ' schedule', _get(day, 'schedule', {}))

def validate_program(program):
    assert_item_data_types('Program day', program, dict)
    for i, day in enumerate(program):
        validate_day('Program day %s' % (i + 1), day)

### Rooms

def validate_rooms(rooms):
    assert_item_data_types('Room', rooms, basestring)

### Consistency checks

def assert_consistency_sessions_persons(sessions, persons):
    for session_id, session in sessions.items():
        chair = session.get('chair', None)
        if chair and chair not in persons:
            error("Session %r chair %r does not exist in persons.yml.", session_id, chair)
        for i, talk in enumerate(_get(session, 'talks')):
            speaker = talk.get('speaker', None)
            if speaker and speaker not in persons:
                error("Session %r talk %s: Speaker %r does not exist in persons register.", 
                    session['id'], i + 1, speaker)
            for j, panel_member in enumerate(_get(talk, 'panel')):
                if panel_member not in persons:
                    error("Session %r talk %s panel member %s %r does not exist in persons register.", 
                        session['id'], i + 1, j + 1, panel_member)

def assert_consistent_workshop_chairs(workshops, persons):
    for workshop_id, workshop in workshops.items():
        for chair, email in _get(workshop, 'chair', {}).items():
            if chair not in persons:
                error("Workshop %r chair %r does not exist in persons.yml.", workshop_id, chair)

def assert_consistent_workshop_rooms(workshops, rooms):
    for workshop_id, workshop in workshops.items():
        room = workshop.get('room', None)
        if room and room not in rooms:
            error("Workshop %r room %r does not exist in rooms.yml.", workshop_id, room)

def assert_consistent_program_workshops(label, day, workshops):
    for slot, activity in _get(workshops, 'schedule', {}).items():
        if activity.lower().startswith('session'):
            starting = activity.split()[1:]
            for id in starting:
                if id not in workshops:
                    error("%s slot %r workshop %r does not exist in workshops.yml.", label, slot, id)

def assert_consistent_program_sessions(label, day, sessions):
    for slot, activity in _get(sessions, 'schedule', {}).items():
        if activity.lower().startswith('session'):
            starting = activity.split()[1:]
            for id in starting:
                if id not in sessions:
                    error("%s slot %r workshop %r does not exist in workshops.yml.", label, slot, id)

### Full integrity check 

def integrity_check(event):
    validate_persons(event['persons'])
    validate_sessions(event['sessions'])
    validate_rooms(event['rooms'])
    validate_workshops(event['workshops'])
    validate_program(event['program'])
    assert_consistency_sessions_persons(event['sessions'], event['persons'])
    assert_consistent_workshop_chairs(event['workshops'], event['persons'])
    assert_consistent_workshop_rooms(event['workshops'], event['rooms'])
    assert_consistent_program_workshops('Program day 1', event['program'][0], event['workshops'])
    assert_consistent_program_workshops('Program day 2', event['program'][1], event['workshops'])
    assert_consistent_program_sessions('Program day 3', event['program'][2], event['sessions'])
    assert_consistent_program_sessions('Program day 4', event['program'][3], event['sessions'])
    
def main(argv=None):
    if argv is None:
        argv = sys.argv
    options, args = Options().parse_args(argv[1:])
    if args:
        return usage("This program takes no arguments.")
    event = load_data(options.datadir)
    integrity_check(event)
    print "OK" 
    #print repr(event['sessions']['cloud']['talks'][2]['title'])
    return 0
    
if __name__ == '__main__':
    sys.exit(main())

