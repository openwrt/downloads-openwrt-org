(function () {
  var loc = location.pathname.replace(/\/$/, "");
  if (!/(\/releases\/[^\/]+|\/snapshots)\/targets$/.test(loc)) return;
  var m = loc.match(/^\/(releases\/[^\/]+|snapshots)\//);
  if (!m) return;
  var overviewUrl = "/" + m[1] + "/.overview.json";
  var basePath = "/" + m[1] + "/targets/";

  var box = document.getElementById("device-search");
  var input = document.getElementById("ds-input");
  var results = document.getElementById("ds-results");
  var status = document.getElementById("ds-status");
  var profiles = null;
  var profilesCache = {};
  box.hidden = false;

  function fetchOverview(cb) {
    if (profiles) {
      cb();
      return;
    }
    status.hidden = false;
    status.textContent = "Loading device list\u2026";
    var x = new XMLHttpRequest();
    x.open("GET", overviewUrl);
    x.onload = function () {
      if (x.status === 200) {
        try {
          profiles = JSON.parse(x.responseText).profiles || [];
        } catch (e) {
          profiles = [];
        }
        status.hidden = true;
        cb();
      } else {
        status.textContent = "Could not load device list.";
      }
    };
    x.onerror = function () {
      status.textContent = "Could not load device list.";
    };
    x.send();
  }

  function fetchProfiles(target, cb) {
    if (profilesCache[target]) {
      cb(profilesCache[target]);
      return;
    }
    var x = new XMLHttpRequest();
    x.open("GET", basePath + target + "/profiles.json");
    x.onload = function () {
      if (x.status === 200) {
        try {
          var d = JSON.parse(x.responseText);
          profilesCache[target] = d;
          cb(d);
        } catch (e) {
          cb(null);
        }
      } else {
        cb(null);
      }
    };
    x.onerror = function () {
      cb(null);
    };
    x.send();
  }

  function fmtSize(n) {
    if (!n) return "-";
    if (n < 1024) return n + " B";
    if (n < 1048576) return (n / 1024).toFixed(1) + " KB";
    return (n / 1048576).toFixed(1) + " MB";
  }

  function showImages(wrap, profile, target) {
    var detail = wrap.querySelector(".ds-detail");
    if (detail) {
      detail.hidden = !detail.hidden;
      return;
    }
    detail = document.createElement("div");
    detail.className = "ds-detail";
    detail.innerHTML =
      '<p class="ds-loading">Loading firmware images\u2026</p>';
    wrap.appendChild(detail);
    fetchProfiles(target, function (data) {
      detail.innerHTML = "";
      if (!data || !data.profiles || !data.profiles[profile]) {
        detail.innerHTML =
          '<p class="ds-loading">Could not load firmware images.</p>';
        return;
      }
      var p = data.profiles[profile];
      if (!p.images || !p.images.length) {
        detail.innerHTML = '<p class="ds-loading">No images available.</p>';
        return;
      }
      var tbl = document.createElement("table");
      var hdr = tbl.insertRow();
      var cols = ["File", "Type", "sha256", "Size"];
      var cls = ["n", "ds-type", "sh", "s"];
      for (var c = 0; c < cols.length; c++) {
        var th = document.createElement("th");
        th.className = cls[c];
        th.textContent = cols[c];
        hdr.appendChild(th);
      }
      for (var i = 0; i < p.images.length; i++) {
        var img = p.images[i];
        var tr = tbl.insertRow();
        var td0 = tr.insertCell();
        td0.className = "n";
        var a = document.createElement("a");
        a.href = basePath + target + "/" + img.name;
        a.textContent = img.name;
        td0.appendChild(a);
        var td1 = tr.insertCell();
        td1.className = "ds-type";
        td1.textContent = img.type || "-";
        var td2 = tr.insertCell();
        td2.className = "sh";
        td2.textContent = img.sha256 || "-";
        td2.title = img.sha256 || "";
        var td3 = tr.insertCell();
        td3.className = "s";
        td3.textContent = fmtSize(img.size);
      }
      detail.appendChild(tbl);
    });
  }

  function render(q) {
    var lq = q.toLowerCase();
    results.innerHTML = "";
    if (!q) {
      return;
    }
    var n = 0;
    for (var i = 0; i < profiles.length && n < 30; i++) {
      var p = profiles[i];
      for (var j = 0; j < p.titles.length; j++) {
        var t = p.titles[j];
        var name =
          t.vendor + " " + t.model + (t.variant ? " " + t.variant : "");
        if (
          name.toLowerCase().indexOf(lq) < 0 &&
          p.id.toLowerCase().indexOf(lq) < 0
        )
          continue;
        var wrap = document.createElement("div");
        wrap.className = "ds-device";
        var hdr = document.createElement("div");
        hdr.className = "ds-device-hdr";
        var nameSpan = document.createElement("span");
        nameSpan.className = "ds-device-name";
        nameSpan.textContent = name;
        var targetSpan = document.createElement("span");
        targetSpan.className = "ds-device-target";
        targetSpan.textContent = p.target;
        hdr.appendChild(nameSpan);
        hdr.appendChild(targetSpan);
        wrap.appendChild(hdr);
        (function (w, pid, tgt) {
          hdr.addEventListener("click", function () {
            showImages(w, pid, tgt);
          });
        })(wrap, p.id, p.target);
        results.appendChild(wrap);
        n++;
        break;
      }
    }
    if (n === 0) {
      status.hidden = false;
      status.textContent = "No devices found.";
    } else {
      status.hidden = true;
    }
  }

  var timer;
  input.addEventListener("input", function () {
    clearTimeout(timer);
    var q = input.value.trim();
    if (q.length < 2) {
      results.innerHTML = "";
      status.hidden = true;
      return;
    }
    timer = setTimeout(function () {
      fetchOverview(function () {
        render(q);
      });
    }, 200);
  });
})();
