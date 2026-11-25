# Append after other NAT hooks. The first terminal rule of an existing NAT
# policy keeps precedence. Only matching UIDs and tether ingress can redirect.
function redirect_rules(c,i,     n,j,skip,devices,target,route,rc,local_count) {
    print "-A " c " ! -p tcp -j RETURN"
    if (hook[i]=="INPUT") return
    if (hook[i]=="OUTPUT") print "-A " c " -o lo -j RETURN"
    if (hook[i]=="PREROUTING") {
        while ((rc=(getline route < local_routes))>0) {
            print "-A " c " -d " route " -j RETURN"
            local_count++
        }
        if (rc<0 || !local_count) exit 2
        close(local_routes)
    }
    print "-A " c " -p tcp --dport 53 -j RETURN"
    print "-A " c " -p tcp --dport 853 -j RETURN"
    if (family=="iptables") {
        n=split("0.0.0.0/8 10.0.0.0/8 100.64.0.0/10 127.0.0.0/8 169.254.0.0/16 172.16.0.0/12 192.0.0.0/24 192.0.2.0/24 192.88.99.0/24 192.168.0.0/16 198.18.0.0/15 198.51.100.0/24 203.0.113.0/24 224.0.0.0/3",skip)
        if (upstream!="" && upstream !~ /:/) print "-A " c " -d " upstream " -j RETURN"
    } else {
        print "-A " c " ! -d 2000::/3 -j RETURN"
        n=split("2001::/23 2001:db8::/32 2002::/16 3fff::/20",skip)
        if (upstream ~ /:/) print "-A " c " -d " upstream " -j RETURN"
    }
    for (j=1;j<=n;j++) print "-A " c " -d " skip[j] " -j RETURN"
    target=(policy=="traffic"?"REDIRECT --to-ports 19870":"DROP")
    if (i==1 || (policy=="guard" && hook[i]=="FORWARD")) {
        n=split("tun+ tailscale+ wg+ warp+ WARP+ ipsec+ xfrm+ ppp+",devices)
        for (j=1;j<=n;j++) print "-A " c " -o " devices[j] " -j RETURN"
    }
    if (i==1) {
        for (j=1;j<=nuid;j++)
            print "-A " c " -p tcp -m owner --uid-owner " uid[j] " -j " target
    } else {
        for (j=1;j<=nif;j++) print "-A " c " -p tcp -i " iface[j] " -j " target
    }
}
