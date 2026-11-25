# Manufacture forward and undo transactions for owned chains only. Input is
# a normalized scope file, then the family snapshot produced by iptables -S.
BEGIN {
    hook[1]="OUTPUT"
    if (policy == "traffic") {
        hook[2]="PREROUTING"; count=2; prefix="MNAP_TCP_"; table="nat"
    } else {
        hook[2]="INPUT"; hook[3]="FORWARD"; count=3; prefix=(policy=="guard"?"MNAP_RGD_":"MNAP_DNS_"); table="filter"
    }
    marker="magicnet-astra-pro." policy ".v1"
    for (i=1; i<=count; i++) {
        chain[i]=prefix hook[i]
        by_name[chain[i]]=i
    }
}
FILENAME == ARGV[1] {
    if ($1 == "uid") uid[++nuid]=$2
    else if ($1 == "tether") iface[++nif]=$2
    else exit 2
    next
}
$1=="-N" { seen[$2]=1; next }
$1=="-A" {
    nr[$2]++
    if ($2 in by_name) {
        before[$2]=before[$2] $0 "\n"
        if ($0 == "-A " $2 " -m comment --comment \"" marker "\" -j RETURN" ||
            $0 == "-A " $2 " -m comment --comment " marker " -j RETURN")
            marked[$2]=1
    }
    for (f=3; f<NF; f++) {
        if (($f == "-j" || $f == "-g") && ($(f+1) in by_name)) {
            ci=by_name[$(f+1)]
            if (NF != 4 || $2 != hook[ci] || $3 != "-j" || at[ci]) conflict=1
            else at[ci]=nr[$2]
        }
    }
}
function drop_rules(c, field, val,   p,k) {
    for (p=1; p<=2; p++) for (k=1; k<=2; k++)
        print "-A " c " " field " " val " -p " (p==1?"udp":"tcp") " --dport " (k==1?53:853) " -j DROP"
}
END {
    for (i=1; i<=count; i++) if (seen[chain[i]] && !marked[chain[i]]) conflict=1
    if (conflict) exit 3
    print "*" table
    for (i=1; i<=count; i++) {
        c=chain[i]; h=hook[i]
        use=(i==1 ? nuid>0 : nif>0)
        if (undo) {
            if (use) print "-D " h " -j " c
            if (use && !seen[c]) { print "-F " c; print "-X " c }
            if (seen[c]) {
                print (use?"-F ":"-N ") c
                printf "%s",before[c]
                if (at[i]) print "-I " h " " at[i] " -j " c
            }
        } else {
            if (at[i]) print "-D " h " -j " c
            if (seen[c]) print "-F " c
            if (use) {
                if (!seen[c]) print "-N " c
                if (policy=="traffic") redirect_rules(c,i)
                else if (i==1) for (u=1; u<=nuid; u++) drop_rules(c,"-m owner --uid-owner",uid[u])
                else for (j=1; j<=nif; j++) drop_rules(c,"-i",iface[j])
                # After successful REDIRECT, filter sees a local destination.
                # Keep blocking eligible direct IPv6 even if NAT later disappears.
                if (policy=="guard" && family=="ip6tables")
                    redirect_rules(c,i)
                print "-A " c " -m comment --comment " marker " -j RETURN"
                if (policy=="traffic") print "-A " h " -j " c
                else print "-I " h " 1 -j " c
            } else if (seen[c]) print "-X " c
        }
    }
    print "COMMIT"
}
