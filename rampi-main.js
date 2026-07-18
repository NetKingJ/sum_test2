var page = new Page();
var csvStatusTimer;
var csvStatus = 1;
$(document).ready(function() {
    var userAgent = window.navigator.userAgent.toLowerCase();
    var safari = /safari/.test( userAgent );
    var ios = /iphone|ipod|ipad/.test( userAgent );

    if( ios && !safari ) {
        $("body").addClass("webview");
    }

    var hasUploadedCSV = $("input[name='hasUploadedCSV']").val() == "true";
    var userId = $("input[name='userId']").val();
    if(hasUploadedCSV && userId) {
        csvStatusTimer = setInterval(function(){
            checkCSVStatus();
        }, 1000);

    }

    if(document.cookie.indexOf("cookie_law_consent") < 0) {
        $(".important-banner--cookies").removeClass("hidden");
    }


    $(".important-banner--updated-terms .important-banner__close").click(function() {
        var that = $(this);
        $.get("/public-scripts/acceptToS", function() {
            that.parent().addClass("hidden");
        });
    });

    $(".important-banner--cookies .important-banner__close").click(function() {
        var date = new Date();
        date.setYear(date.getFullYear()+1)
        var dateString = date.toUTCString();
        var cookieString = "cookie_law_consent=1;expires="+dateString+";domain=.flightradar24.com;path=/";
        document.cookie = cookieString;
        $(this).parent().addClass("hidden");

    });

if($("body").hasClass("webview")) {
    $("body").find("footer.footer").hide();
}

  $('.nav .menu-button').click(function() {
    page.toggleSideMenu($(this));
  });
  $('.header .sidebar-fadeout').click(function() {
    page.hideSideMenu($('.nav .menu-button'));
  });

  $(document).keyup(function(e) {
    if(e.keyCode == 27) {
      var menuButton = $('.nav .menu-button');
      if($(menuButton).hasClass('collapsed')) {
        page.hideSideMenu(menuButton);
      }
    }
  });

  $('.tooltip').hover(
    function() {
      page.showTooltip($(this));
    },
    function() {
      page.hideTooltip();
    }
  );

  $("body").on("click", ".body-notification i.fa", function() {
        if($(".body-notification").hasClass("csv")) {
            clearInterval(csvStatusTimer);
        }
		page.closeNotification();
	});

  $("body").on("click", ".signOutLink", function() {
    page.signOut($(this).attr("data-url"));
  });

  $('#facebook-signin, .facebook-signin').click(function() {
	if( fbInit == '1' ) {
		window.location = site_url + '/connect-with-facebook';
	} else {
		FB.login(function(response) {
				if (response.authResponse) {

					window.location = site_url + '/connect-with-facebook';
				}
			},
			{scope:'email,publish_actions'}
		);
	}
});

$('#facebook-signout').click(function() {
	signout();
	return false;
});


});

function checkCSVStatus() {
    $.get("/public-scripts/csv-status", function(data) {
        if(data.statusNum > 1) {
            var text = "CSV file upload status: " + data.statusText;
            if($(".body-notification").length <= 0) {
                page.showNotification(text, 0, "csv");
            } else {
                page.setNotificationText(text);
            }
        } else {
            page.setNotificationText("Your CSV upload has completed");
            clearInterval(checkCSVStatus);
        }
    });

}

/*
 * Page class
 */
function Page() {
  // Properties
  this._notificationTimeout = null;
  this._initRun = false;

  if(typeof myfr24Init === 'function' && !this._initRun) {
    myfr24Init();
    this._initRun = true;
  }

};

Page.prototype.toggleSideMenu = function(menuButton) {
  if($(menuButton).hasClass('collapsed')) {
    this.hideSideMenu(menuButton);
  }
  else {
    this.showSideMenu(menuButton);
  }
};

Page.prototype.showSideMenu = function(menuButton) {
  $(menuButton).addClass('collapsed');
  $('.header .sidebar-fadeout').fadeIn(100);
  $('.header .sidebar-nav').fadeIn(150);
  $('html, body').scrollTop(0);
  $('body').addClass('no-scroll');
};

Page.prototype.hideSideMenu = function(menuButton) {
  $(menuButton).removeClass('collapsed');
  $('.header .sidebar-fadeout').fadeOut();
  $('.header .sidebar-nav').fadeOut();
  $('body').removeClass('no-scroll');
};

Page.prototype.showTooltip = function(element) {
  var offset = element.offset();
  var content = $(element).attr('data-tooltip-value');
  $('body').append('<div class="tooltip-overlay" style="top: ' + (offset.top + 25) + 'px; left: ' + offset.left + 'px;"><div class="arrow"></div><div class="inner">' + content + '</div></div>');
};

Page.prototype.hideTooltip = function(element) {
  $('.tooltip-overlay').remove();
};

Page.prototype.setNotificationText = function(text) {
    $(".body-notification .container .text").html('<i class="fa fa-times close"></i>'+text);
};

Page.prototype.showNotification = function(text, timeout, color) {
	this.removeNotification();
	var prepend_html = '<div class="body-notification ' + color + '"><div class="container"><div class="text"><i class="fa fa-times close"></i>' + text + '</div></div></div>';
	$(prepend_html).prependTo("body").hide().slideDown(200, function() {
		$(".text", $(this)).fadeIn(200);
	});

	if(timeout > 0) {
		this._notificationTimeout = setTimeout(function() { page.closeNotification() }, timeout);
	}
};

Page.prototype.closeNotification = function() {
	$(".body-notification").animate({opacity:0}, 500, function() {
		this.remove();
	});
  clearTimeout(this._notificationTimeout);
};

Page.prototype.removeNotification = function() {
	$(".body-notification").remove();
};

Page.prototype.signOut = function(url) {
  $.get( url );
};
