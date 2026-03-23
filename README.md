# boybot2000
Discord bot that shows weather, moons states, upcoming & current guild events, and meows.  
  
Weather functionality based on https://github.com/ethanocurtis/Weather-Bot.  
Event scraping functionality from https://lud.ink/ and https://github.com/atomriot.  

# Commands
## events_subscriptions
Sends a list of subscriptions a user has for events in the current channel to the user that requested it.

## events_subscribe (utc time, cadence)
Subscribes the current channel to event announcements at a specified interval.

## events_unsubscribe (subscriptionId)
Cancels a subscription to event announcements.

## events_list
Posts a list of current events in the current channel for everyone to see.

## weather_current
## weather_hourly
## weather_subscriptions
## weather_subscribe
## weather_unsubscribe
## weather_alerts

## moon
Replies with the current moon state.