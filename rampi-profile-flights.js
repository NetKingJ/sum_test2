
var flightList = new FlightList;
var isSticky = false;
$(document).ready(function() {

  $(document).on("mouseover", '.flight-list tr', function(){
    if($(this).find(".inner-actions").length > 0) {
        $(this).addClass('hovered');
    }
});

 $(document).on("mouseleave", '.flight-list tr', function(){
      $(this).removeClass('hovered');
});

  $('.main').prepend(
    '<div class="flight-list-outer-header"><div class="flight-list-header container profile-flights-container"><table class="flight-list"><tbody>'
    + $('.flight-list-original thead').html()
    + '</tbody></table></div></div>'
  );

  flightList.fixThWidths();

  $(window).scroll(function() {
    if($(window).scrollTop() >= 60 && !isSticky) {
      isSticky = true;
      $('.flight-list-outer-header').addClass('fixed');
      $('.flight-list-original').addClass('hasStickyHeader');
    }
    else if($(window).scrollTop() < 60 && isSticky) {
      isSticky = false;
      $('.flight-list-outer-header').removeClass('fixed');
      $('.flight-list-original').removeClass('hasStickyHeader');
    }
  });

  var resizeThrottle;
  $(window).resize(function() {
    clearTimeout(resizeThrottle);
    resizeThrottle = setTimeout(flightList.fixThWidths, 500);
  });
  var loading_more = 0;

  $("#flight-list-more").click(function() {
  	if(loading_more==0) {
  		loading_more = 1;
  		var user = $("table.flight-list-original").attr("data-list-user");
  		var order = $("table.flight-list-original").attr("data-list-order");
  		var unit = $("table.flight-list-original").attr("data-list-order-unit");
  		var last_row = $("table.flight-list-original tr").last().attr("data-row-number");

  		$.getJSON('/public-scripts/flight-list/'+user+'/'+last_row+'/'+order+'/'+unit, function(data) {
  			json_index = [];
    		$.each(data, function(key, val) {
  				json_index.push(key);
  			});
  			if(json_index.length>0) {
  				var append_html = '';
  				var x = 1;
  				var total = json_index.length;
  				for(var j in json_index) {
  					i = json_index[j];
  					append_html += '<tr class="'+(i%2 ? 'odd' : '')+' '+(x==total ? 'last' : '')+'" data-row-number="'+i+'">';
                    append_html += '<td class="flight-date">'+data[i][0]+'</td><td class="flight-flight">'+data[i][1]+'</td><td class="flight-reg">'+data[i][9]+'</td><td class="flight-from">'+data[i][2]+'</td><td class="flight-to">'+data[i][3]+'</td>';
                    append_html += '<td class="flight-distance">'+data[i][4]+'</td><td class="flight-dep-time">'+data[i][5]+'</td><td class="flight-arr-time">'+data[i][6]+'</td>';
                    append_html += '<td class="flight-airline">'+data[i][7]+'</td><td class="flight-aircraft">'+data[i][8]+'</td>';
                    append_html += '<td class="flight-seat">'+data[i][10]+'</td><td class="flight-note">'+data[i][11]+'</td>';
                    append_html += '<td class="flight-icons">'+data[i][12]+'</td></tr>';
  					x++;
  				}
  				$("table.flight-list-original tr").removeClass("last");
  				$("table.flight-list-original > tbody").append(append_html);
  			}
            if(data.length <= 0) {
                $("#flight-list-more").hide();
            }
  			loading_more = 0;
  		});
  	}
  });


});


/*
 * Flight list class
 */
function FlightList() {
  // Properties


};

FlightList.prototype.fixThWidths = function() {
  var headerTds = $('.flight-list-header .flight-list tr th');
  var originalTds = $('.flight-list-original tbody tr:first td');
  $(originalTds).each(function(index, td) {
    $(headerTds).eq(index).css('width', Math.round($(td).width()) + 'px');

  })
};
