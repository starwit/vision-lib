def is_sae_message(msg: 'SaeMessage') -> bool:
    '''This function takes an 'SaeMessage' object and tries to determine if it is a valid 
       'SaeMessage' by checking it for mandatory fields.'''
    return all((
        msg.HasField('frame'),
        msg.frame.source_id != '',
        msg.frame.timestamp_utc_ms != 0,
        msg.frame.HasField('shape'),
        msg.HasField('metrics')
    ))

def is_position_message(msg: 'PositionMessage') -> bool:
    '''This function takes an 'PositionMessage' object and tries to determine if it is a valid 
       'PositionMessage' by checking it for mandatory fields.'''
    return all((
        msg.HasField('geo_coordinate'),
        msg.timestamp_utc_ms != 0,
    ))