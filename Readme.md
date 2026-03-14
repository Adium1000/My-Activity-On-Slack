# My Activity On Slack

![THUMB](Github_Assets/Devlogs/NEW.png)

- A simple Python app that sinks your activity with you Slack status!

![alt text](Github_Assets/Guide/guide.png)

Watch on [Youtube](https://www.youtube.com/watch?v=rLFpijAMtlY)

- First download the app from releases !

### Get Slack Token 

- Go to [Slack Aps](https://api.slack.com/apps)

- Click Create New App -> From scratch

![FromScratch](<Github_Assets/Guide/from_scratch.png>)

- Give it a name (status)

![Name](Github_Assets/Guide/work.png)

- Now go to the OAuth & Permissions
- Scroll to User Token Scopes and add `users.profile:write`

![token](Github_Assets/Guide/uatoken.png)

- Now go to the start of the page and click Install to workspace -> Allow

![alt text](Github_Assets/Guide/install_slack_app.png)

- Copy User OAuth Token

![Spotify API (PREMIUM)](Github_Assets/Guide/spotify.png)

- Go to: [Spotify Developer Dashboard](https://developer.spotify.com/dashboard)

- Login to your Spotify Account if you aren't logged 

- Accept the TOS

![tos](Github_Assets/Guide/tos.png)


- Now click on the Create App button

![alt text](Github_Assets/Guide/createapp.png)

 - Put a name (slack-status)
 - Redirect URI: http://127.0.0.1:9090/callback
 - Check WEB API

![api](Github_Assets/Guide/web_api_config.png)

- After that go to the app settings and copy CLIENT ID and CLIENT SECRET

![bi](Github_Assets/Guide/bi.png)


![apps](Github_Assets/Guide/appps.png)

- You can config other apps too just click on the add button on the section "Other Aps"
- You can also arrange the priority order from the right top of the item

![alt text](Github_Assets/Guide/Slack.png)

- After you create a new entery here just give it a name

![new](Github_Assets/Guide/NEW.png)

- Then choose a status text and an emoji 

![Config](Github_Assets/Guide/stand.png)

- Now click detect process and choose the app process

![process](Github_Assets/Guide/app.png)

- Please note that if you OAuth Spotify, Spotify has priority of showing

![IDs](Github_Assets/Guide/ids.png)
- To sync your status on Slack, you need to paste the codes we discussed into the app

![codes](Github_Assets/Guide/codes.png)

![resource](Github_Assets/Guide/res.png)

- This app uses less then 50MB RAM

![Credits](Github_Assets/Guide/credits.png)

!!! All logos for other apps belong to their respective developers and are not owned by me, such as the logos for: Spotify, VSC, VLC, Chrome, Slack !!!


