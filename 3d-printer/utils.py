def log_event(log, env, component, event_type, details=None):
    log.append({
        'time': env.now,
        'component': component,
        'event_type': event_type,
        'details': details or {}
    })