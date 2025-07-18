#!/bin/bash

sed -En '/.*<(latitude|longitude)>(-?[0-9.]+)<\/(latitude|longitude)>/s//\2/p' | awk '
NR%2==1 { lats[length(lats)] = $1 }
NR%2==0 { lons[length(lons)] = $1 }
END {
  print "{\"type\": \"Feature\", \"geometry\": {\"type\": \"LineString\", \"coordinates\": ["
  for (i = 0; i < length(lats); i++) {
    if (i > 0) printf ","
    printf "[%s, %s]\n", lons[i], lats[i]
  }
  print "]},\"properties\":{}}"
}'
