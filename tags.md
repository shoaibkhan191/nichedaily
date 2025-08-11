---
layout: default
title: Tags
permalink: /tags/
---

# Tags

{% assign tags = site.tags | sort %}

{% for tag in tags %}

## #{{ tag[0] }}

{% for post in tag[1] %}

- [{{ post.title }}]({{ post.url | relative_url }}) ({{ post.date | date: '%Y-%m-%d' }})

{% endfor %}

{% endfor %}

