#!/bin/sh

# Find a grafana pod
pod=$(kubectl get pods -l app.kubernetes.io/name=grafana -o=jsonpath='{.items[0].metadata.name}')

if [ -z "$pod" ]; then
    echo "No pod found with the specified label."
    exit 1
fi

# Kill the plugin backend process so Grafana restarts it. Grafana 13.3+ images have no bash.
# pkill exits 1 only when nothing matched; kubectl exec failures still fail this script.
kubectl exec "$pod" -- sh -c 'pkill gpx_grafana || { [ $? -eq 1 ] && echo "No gpx_grafana process found."; }'
