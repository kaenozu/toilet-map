/**
 * static/popup_fix.js
 * Leaflet popup position fix for Streamlit iframe environment.
 * Searches for the Leaflet map instance in window scope and adjusts
 * popup position when it opens to prevent overflow outside the map bounds.
 */
(function(){
  function fixPopups(){
    var mapEl = document.getElementById('map');
    if(!mapEl) { setTimeout(fixPopups, 500); return; }
    var lmap = null;
    for(var k in window){
      try{ if(window[k] && window[k].getContainer && window[k].getContainer()===mapEl){ lmap=window[k]; break; } }catch(e){}
    }
    if(!lmap){ setTimeout(fixPopups, 500); return; }

    lmap.on('popupopen', function(e){
      setTimeout(function(){
        var popup = e.popup._container;
        if(!popup) return;
        var mapRect = lmap.getContainer().getBoundingClientRect();
        var popRect = popup.getBoundingClientRect();
        if(popRect.left < mapRect.left + 8){
          popup.style.left = (mapRect.left + 8 - popRect.left + parseFloat(popup.style.left||0)) + 'px';
        }
        if(popRect.right > mapRect.right - 8){
          popup.style.left = (parseFloat(popup.style.left||0) - (popRect.right - mapRect.right + 8)) + 'px';
        }
        if(popRect.top < mapRect.top + 8){
          var dy = mapRect.top + 8 - popRect.top;
          lmap.panBy([0, -dy], {animate: true, duration: 0.2});
        }
        if(popRect.bottom > mapRect.bottom - 8){
          var dy = popRect.bottom - mapRect.bottom + 8;
          lmap.panBy([0, dy], {animate: true, duration: 0.2});
        }
      }, 50);
    });
  }
  fixPopups();
})();
