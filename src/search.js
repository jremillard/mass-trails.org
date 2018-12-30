"use strict";

var Fuse = require('fuse.js')
var searchData = require('./search.json')

var fuse = null

function doSearch(text) {
    var results = fuse.search(text);
    
    var elem = document.getElementById('result');
    var display = ""
    for (var i = 0; i < results.length; i++) {
        var result = results[i]
        switch ( result.type  ) {
            case 'T':
                display += "<li><a href=\"" + result.url + "\">" + result.show + "</li>";                
                break;

            case 'P':            
                display += "<li><a href=\"" + result.url + "\">" + result.search + "</a> property "
                display += " in " + result.town + ". ";
                if ( result.publicTrailLength > 0.05) {
                    display += result.publicTrailLength.toFixed(1) + " miles of trails, and "
                    display += result.propertyArea.toFixed(0) + " acres of land."                                    
                } else  {
                    display += " No public trails and " + result.propertyArea.toFixed(0) + " acres of land."                                    
                }
                display += "</li>"
                break;

            case 'L':
                display += "<li><a href=\"" + result.url + "\">" + result.search + "</a> Landowner</li>";        
                break;
        }
    }
    elem.innerHTML = display    
}
      
function searchChange(inputText) {
    if ( fuse == null) {
        var options = {
            keys: ['search'],
            shouldSort: true,
            threshold: 0.2,
            }

        fuse = new Fuse(searchData, options);        
    }

    doSearch(inputText)        
}

window.searchChange = searchChange

