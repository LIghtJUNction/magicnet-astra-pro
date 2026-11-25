# Manufacture forward and undo transactions for the filter table only. Input is
# a normalized scope file, then the family snapshot produced by iptables -S.
BEGIN {
    hook[1]="OUTPUT"; hook[2]="INPUT"; hook[3]="FORWARD"
    for (i=1; i<=3; i++) {
        chain[i]="MNAP_DNS_" hook[i]
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
        if ($0 == "-A " $2 " -m comment --comment \"magicnet-astra-pro.dns.v1\" -j RETURN" ||
            $0 == "-A " $2 " -m comment --comment magicnet-astra-pro.dns.v1 -j RETURN")
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
    for (i=1; i<=3; i++) if (seen[chain[i]] && !marked[chain[i]]) conflict=1
    if (conflict) exit 3
    print "*filter"
    for (i=1; i<=3; i++) {
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
                if (i==1) for (u=1; u<=nuid; u++) drop_rules(c,"-m owner --uid-owner",uid[u])
                else for (j=1; j<=nif; j++) drop_rules(c,"-i",iface[j])
                print "-A " c " -m comment --comment magicnet-astra-pro.dns.v1 -j RETURN"
                print "-I " h " 1 -j " c
            } else if (seen[c]) print "-X " c
        }
    }
    print "COMMIT"
}
